"""The morning check (S37, #141): when it runs, what it does, what it says."""

from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from book_watch import daily, db, enrichment, wantlist
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import Listing, Money

BOOKS = {
    "9781590171998": "Stoner",
    "9780099448396": "Crash",
    "9781771965231": "Breaking and Entering",
}

# 7am in New York is 11:00 UTC in summer and 12:00 UTC in winter.
SUMMER_SEVEN = datetime(2026, 7, 1, 11, 0, tzinfo=UTC)
WINTER_SEVEN = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def connect(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    with closing(connect()) as connection:
        for isbn, title in BOOKS.items():
            wantlist.add(connection, isbn, title)
        connection.commit()
    return connect


def listings(query, limit, **_):
    return [
        Listing(
            item_id=f"{query}|{n}",
            title=f"{BOOKS[query]} a fine copy",
            price=Money(Decimal(f"{10 + n}.00"), "USD"),
            item_web_url="https://www.ebay.com/itm/1",
            condition="Good",
            seller="seller",
            shipping_cost=Money(Decimal("0.00"), "USD"),
            thumbnail_url=None,
            listing_date=datetime(2026, 9, 1, tzinfo=UTC),
        )
        for n in range(3)
    ]


def nothing_spent():
    return 0


def record(connect, started, finished=None, outcome=None, books=3, failed=0):
    with closing(connect()) as connection:
        connection.execute(
            "INSERT INTO daily_run (started_at, finished_at, outcome, books, failed) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                daily._stored(started),
                daily._stored(finished) if finished else None,
                outcome,
                books,
                failed,
            ),
        )
        connection.commit()


def runs(connect):
    with closing(connect()) as connection:
        return connection.execute("SELECT * FROM daily_run ORDER BY id").fetchall()


# --- when it runs -----------------------------------------------------------


@pytest.mark.parametrize("seven", [SUMMER_SEVEN, WINTER_SEVEN])
def test_it_is_due_at_seven_new_york_time_in_summer_and_winter(connect, seven):
    with closing(connect()) as connection:
        assert not daily.due(connection, seven - timedelta(minutes=1))
        assert daily.due(connection, seven)


def test_it_is_not_due_again_once_todays_run_finished(connect):
    record(connect, SUMMER_SEVEN, SUMMER_SEVEN + timedelta(minutes=5), "ok")

    with closing(connect()) as connection:
        assert not daily.due(connection, SUMMER_SEVEN + timedelta(hours=3))


def test_yesterdays_run_does_not_count_for_today(connect):
    yesterday = SUMMER_SEVEN - timedelta(days=1)
    record(connect, yesterday, yesterday + timedelta(minutes=5), "ok")

    with closing(connect()) as connection:
        assert daily.due(connection, SUMMER_SEVEN + timedelta(minutes=1))


def test_a_run_cut_off_by_a_restart_is_owed_again(connect):
    """Started and never finished: the app went down mid-run."""
    record(connect, SUMMER_SEVEN)

    with closing(connect()) as connection:
        assert daily.due(connection, SUMMER_SEVEN + timedelta(hours=3))


def test_a_tick_runs_only_when_due(connect):
    asked = []

    def search(query, limit, **kwargs):
        asked.append(query)
        return listings(query, limit)

    six = SUMMER_SEVEN - timedelta(hours=1)
    early = daily.tick(connect, search, lambda w: None, nothing_spent, six)
    on_time = daily.tick(connect, search, lambda w: None, nothing_spent, SUMMER_SEVEN)

    assert early is None
    assert on_time is not None
    assert len(asked) == 3


# --- what a run does --------------------------------------------------------


def test_a_run_searches_every_book_and_examines_what_it_found(connect):
    asked, examined = [], []

    def search(query, limit, **kwargs):
        asked.append(query)
        return listings(query, limit)

    def examine(work_id):
        # The row says digging while this runs.
        assert enrichment.busy(work_id)
        examined.append(work_id)

    daily.run(connect, search, examine, nothing_spent)

    assert sorted(asked) == sorted(BOOKS)
    assert len(examined) == 3
    [done] = runs(connect)
    assert done["outcome"] == "ok"
    assert done["books"] == 3
    assert done["finished_at"] is not None


def test_each_book_is_examined_before_the_next_is_searched(connect):
    """One request in flight at a time, across both services."""
    order = []

    def search(query, limit, **kwargs):
        order.append("search")
        return listings(query, limit)

    daily.run(connect, search, lambda w: order.append("examine"), nothing_spent)

    assert order == ["search", "examine"] * 3


def test_a_failed_search_is_counted_and_the_run_carries_on(connect):
    asked = []

    def search(query, limit, **kwargs):
        asked.append(query)
        if query == "9780099448396":
            raise EbaySearchError("eBay said no")
        return listings(query, limit)

    daily.run(connect, search, lambda w: None, nothing_spent)

    assert len(asked) == 3
    [done] = runs(connect)
    assert done["outcome"] == "failed"
    assert done["failed"] == 1


def test_a_pass_stopped_by_the_ceiling_marks_the_run_throttled(connect):
    def examine(work_id):
        return enrichment.Pass(stopped_because="over budget")

    daily.run(connect, listings, examine, nothing_spent)

    assert runs(connect)[0]["outcome"] == "throttled"


def test_a_run_records_what_it_spent_of_the_open_library_ceiling(connect):
    spent = iter([100, 112, 112])

    daily.run(connect, listings, lambda w: None, lambda: next(spent))

    assert runs(connect)[0]["openlibrary_spent"] == 12


def test_a_run_that_crashes_still_records_itself_as_failed(connect):
    def examine(work_id):
        raise RuntimeError("something nobody expected")

    with pytest.raises(RuntimeError):
        daily.run(connect, listings, examine, nothing_spent)

    [done] = runs(connect)
    assert done["outcome"] == "failed"
    assert done["finished_at"] is not None


# --- what the want list says ------------------------------------------------


def test_nothing_is_said_when_this_mornings_run_went_well(connect):
    record(connect, SUMMER_SEVEN, SUMMER_SEVEN + timedelta(minutes=5), "ok")

    with closing(connect()) as connection:
        assert daily.status(connection, SUMMER_SEVEN + timedelta(hours=5)) is None


def test_a_failed_run_says_how_many_books_it_missed(connect):
    record(
        connect, SUMMER_SEVEN, SUMMER_SEVEN + timedelta(minutes=5), "failed", failed=2
    )

    with closing(connect()) as connection:
        said = daily.status(connection, SUMMER_SEVEN + timedelta(hours=5))

    assert said.label == "Daily check failed"
    assert "couldn't search 2 of 3 books" in said.explanation
    assert "Jul 1 at 7:05am" in said.explanation


def test_a_throttled_run_says_so(connect):
    record(connect, SUMMER_SEVEN, SUMMER_SEVEN + timedelta(minutes=5), "throttled")

    with closing(connect()) as connection:
        said = daily.status(connection, SUMMER_SEVEN + timedelta(hours=5))

    assert said.label == "Daily check throttled"


def test_no_run_for_over_a_day_says_it_didnt_run(connect):
    record(connect, SUMMER_SEVEN, SUMMER_SEVEN + timedelta(minutes=5), "ok")

    with closing(connect()) as connection:
        said = daily.status(connection, SUMMER_SEVEN + timedelta(hours=27))

    assert said.label == "Daily check didn't run"


def test_no_run_ever_says_it_didnt_run(connect):
    with closing(connect()) as connection:
        said = daily.status(connection, SUMMER_SEVEN)

    assert said.label == "Daily check didn't run"
    assert "No daily check has run yet" in said.explanation


def test_nothing_is_said_while_a_run_is_going(connect):
    yesterday = SUMMER_SEVEN - timedelta(days=2)
    record(connect, yesterday, yesterday + timedelta(minutes=5), "ok")
    record(connect, SUMMER_SEVEN)

    with closing(connect()) as connection:
        assert daily.status(connection, SUMMER_SEVEN + timedelta(minutes=10)) is None

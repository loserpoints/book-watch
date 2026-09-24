"""Tests for the background pass over a book's copies.

Nothing here reaches a network: `tests/conftest.py` makes that a loud failure,
and every client is a counting stub so the tests can assert *how much* was
asked rather than only what came back.
"""

import pytest

from book_watch import db, enrichment
from book_watch.ebay.declarations import Declarations
from book_watch.ebay.detail import Declared
from book_watch.ebay.errors import EbaySearchError
from book_watch.openlibrary import BudgetExhausted, OpenLibraryUnavailable
from book_watch.openlibrary.models import EditionIdentity

STONER = EditionIdentity(
    isbn="9781590171998",
    title="Stoner",
    work_id="OL3511459W",
    publisher="New York Review Books",
    published="2006",
    physical_format="Trade Paperback",
)
OMNIBUS = EditionIdentity(
    isbn="9781598537024",
    title="John Williams : Collected Novels",
    work_id="OL26589081W",
    publisher="Library of America",
    published="2021",
    physical_format=None,
)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    connection = connect()
    connection.execute("INSERT INTO work (id, title) VALUES (1, 'Stoner')")
    connection.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'reader')")
    connection.commit()
    yield connect, connection
    connection.close()


def a_copy(connection, item_id):
    connection.execute(
        "INSERT INTO copy (item_id, work_id, title, url, price, currency) "
        "VALUES (?, 1, 'Stoner', 'https://ebay/x', '9.99', 'USD')",
        (item_id,),
    )
    connection.commit()


class CountingDetail:
    def __init__(self, answers, fail_after=None):
        self.answers = answers
        self.fail_after = fail_after
        self.asked = []

    def declared_by(self, item_id):
        if self.fail_after is not None and len(self.asked) >= self.fail_after:
            raise EbaySearchError("ebay is down")
        self.asked.append(item_id)
        return self.answers.get(item_id, Declared(item_id))


class CountingResolver:
    def __init__(self, connection, answers, raises=None, raise_after=None):
        self._connection = connection
        self.answers = answers
        self.raises = raises
        self.raise_after = raise_after
        self.asked = []

    def known(self, isbn):
        row = self._connection.execute(
            "SELECT 1 FROM openlibrary_edition WHERE isbn = ?", (isbn,)
        ).fetchone()
        return row is not None

    def identify(self, isbn):
        if self.raises and (
            self.raise_after is None or len(self.asked) >= self.raise_after
        ):
            raise self.raises
        self.asked.append(isbn)
        found = self.answers.get(isbn)
        self._connection.execute(
            "INSERT OR IGNORE INTO openlibrary_edition (isbn, found, title) "
            "VALUES (?, ?, ?)",
            (isbn, 1 if found else 0, found.title if found else None),
        )
        return found


def run(database, detail, resolver_answers, **resolver_kwargs):
    connect, connection = database
    resolver = CountingResolver(connection, resolver_answers, **resolver_kwargs)
    result = enrichment.enrich(
        connect,
        1,
        lambda conn: Declarations(conn, detail),
        lambda conn: resolver,
    )
    return result, resolver


def test_a_pass_examines_every_copy_and_resolves_every_number(database):
    _, connection = database
    a_copy(connection, "v1|1|0")
    a_copy(connection, "v1|2|0")
    detail = CountingDetail(
        {
            "v1|1|0": Declared("v1|1|0", isbn="9781590171998"),
            "v1|2|0": Declared("v1|2|0", isbn="9781590171998"),
        }
    )

    result, resolver = run(database, detail, {"9781590171998": STONER})

    assert result.completed
    assert result.examined == 2
    # Both copies declared the same number, so it is asked about once.
    assert resolver.asked == ["9781590171998"]


def test_a_number_the_catalogue_says_is_this_book_becomes_an_edition(database):
    """So the next copy declaring it is certain without asking anything."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert result.editions_learned == 1
    row = connection.execute(
        "SELECT isbn, publisher FROM edition WHERE work_id = 1"
    ).fetchone()
    assert row["isbn"] == "9781590171998"
    assert row["publisher"] == "New York Review Books"


def test_a_number_naming_a_different_book_does_not_become_an_edition(database):
    """The omnibus. Its title contains the book's and its author is right."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781598537024")})

    result, _ = run(database, detail, {"9781598537024": OMNIBUS})

    assert result.editions_learned == 0
    assert connection.execute("SELECT count(*) AS n FROM edition").fetchone()["n"] == 0


def test_a_finished_pass_is_recorded_so_the_want_list_stops_saying_so(database):
    _, connection = database
    a_copy(connection, "v1|1|0")

    run(database, CountingDetail({}), {})

    row = connection.execute("SELECT enriched_at FROM work WHERE id = 1").fetchone()
    assert row["enriched_at"] is not None


def test_a_second_pass_learns_nothing_new_and_asks_ebay_nothing(database):
    """Everything a pass learns is written down, so the next one is free.

    The resolver is asked again, and answers from its own notebook without
    reaching Open Library — which `test_openlibrary.py` is what proves. What
    is asserted here is that nothing *new* was learned, and that eBay was not
    troubled a second time at all.
    """
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})

    run(database, detail, {"9781590171998": STONER})
    second, _ = run(database, detail, {"9781590171998": STONER})

    assert detail.asked == ["v1|1|0"]
    assert second.examined == 0
    assert second.resolved == 0
    assert second.editions_learned == 0


# --- stopping, which has to leave things usable ------------------------------


def test_the_ceiling_stops_the_pass_rather_than_being_retried(database):
    """Decision 39: retrying this on a timer is the exact failure it prevents."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})

    result, resolver = run(
        database, detail, {}, raises=BudgetExhausted("500 today"), raise_after=0
    )

    assert not result.completed
    assert result.stopped_because == "over budget"
    assert resolver.asked == []


def test_open_library_going_down_leaves_what_was_learned(database):
    _, connection = database
    a_copy(connection, "v1|1|0")
    a_copy(connection, "v1|2|0")
    detail = CountingDetail(
        {
            "v1|1|0": Declared("v1|1|0", isbn="9781590171998"),
            "v1|2|0": Declared("v1|2|0", isbn="9781598537024"),
        }
    )

    result, _ = run(
        database,
        detail,
        {"9781590171998": STONER},
        raises=OpenLibraryUnavailable("down"),
        raise_after=1,
    )

    assert not result.completed
    # The eBay half finished and is kept: the next pass will not redo it.
    assert (
        connection.execute("SELECT count(*) AS n FROM listing_declaration").fetchone()[
            "n"
        ]
        == 2
    )


def test_an_unfinished_pass_is_not_recorded_as_finished(database):
    """Otherwise the want-list would stop saying so while work remained."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})

    run(database, detail, {}, raises=BudgetExhausted("500 today"), raise_after=0)

    row = connection.execute("SELECT enriched_at FROM work WHERE id = 1").fetchone()
    assert row["enriched_at"] is None


def test_ebay_going_down_stops_the_pass_without_losing_the_copies_it_examined(database):
    _, connection = database
    a_copy(connection, "v1|1|0")
    a_copy(connection, "v1|2|0")
    detail = CountingDetail(
        {"v1|1|0": Declared("v1|1|0", isbn="9781590171998")}, fail_after=1
    )

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert result.stopped_because == "ebay unavailable"
    assert (
        connection.execute("SELECT count(*) AS n FROM listing_declaration").fetchone()[
            "n"
        ]
        == 1
    )


def test_two_passes_on_one_book_do_not_both_run(database):
    """A page refresh mid-pass would otherwise ask everything twice."""
    connect, connection = database
    a_copy(connection, "v1|1|0")
    enrichment._in_progress.add(1)
    try:
        result = enrichment.enrich(connect, 1, lambda c: None, lambda c: None)
    finally:
        enrichment._in_progress.discard(1)

    assert result.stopped_because == "already running"


def test_a_book_that_is_gone_is_not_an_error(database):
    connect, _ = database

    result = enrichment.enrich(connect, 999, lambda c: None, lambda c: None)

    assert result.stopped_because == "no such book"


# --- a book that was never identified --------------------------------------
#
# Every book added by number during M1 sits in this state: migration 003
# carried it across with no title, migration 004 gave it a null `resolved_at`,
# and only the *add* path ever writes that column. The want-list reads
# "Looking this up…" for ever, and nobody is.


def an_untitled_book(connection, isbn="9780679726197"):
    connection.execute("INSERT INTO work (id) VALUES (2)")
    connection.execute(
        "INSERT INTO entry (work_id, hunt, typed) VALUES (2, 'reader', ?)", (isbn,)
    )
    connection.commit()


def test_a_pass_gives_an_untitled_book_its_title(database):
    connect, connection = database
    an_untitled_book(connection)
    resolver = CountingResolver(connection, {"9780679726197": STONER})

    result = enrichment.enrich(
        connect, 2, lambda c: Declarations(c, CountingDetail({})), lambda c: resolver
    )

    assert result.identified
    row = connection.execute(
        "SELECT title, resolved_at FROM work WHERE id = 2"
    ).fetchone()
    assert row["title"] == "Stoner"
    assert row["resolved_at"] is not None


def test_a_book_the_catalogue_cannot_identify_stops_saying_it_is_being_looked_up(
    database,
):
    """Asked, and there is no answer. Claiming somebody is still looking
    would no longer be true."""
    connect, connection = database
    an_untitled_book(connection, "9788925538297")
    resolver = CountingResolver(connection, {"9788925538297": None})

    enrichment.enrich(
        connect, 2, lambda c: Declarations(c, CountingDetail({})), lambda c: resolver
    )

    row = connection.execute(
        "SELECT title, resolved_at FROM work WHERE id = 2"
    ).fetchone()
    assert row["title"] is None
    assert row["resolved_at"] is not None


def test_a_book_that_already_has_a_title_is_left_alone(database):
    _, connection = database
    a_copy(connection, "v1|1|0")

    result, _ = run(database, CountingDetail({}), {})

    assert not result.identified


def test_a_number_a_seller_attributes_to_someone_else_is_not_learned(database):
    """The strictest check in the app, and the reason is asymmetric.

    An edition learned wrongly is not one bad listing — it is a number that
    makes every future listing declaring it *certain*, ahead of any other
    evidence. That is how Don Gillmor's *Breaking and Entering* became an
    edition of Joy Williams's.
    """
    _, connection = database
    connection.execute("UPDATE work SET author = 'Joy Williams' WHERE id = 1")
    connection.execute("UPDATE work SET title = 'Breaking and Entering' WHERE id = 1")
    a_copy(connection, "v1|1|0")
    connection.commit()
    detail = CountingDetail(
        {"v1|1|0": Declared("v1|1|0", isbn="9781771965231", author="Don Gillmor")}
    )
    gillmor = EditionIdentity(
        isbn="9781771965231",
        title="Breaking and Entering",
        work_id="OL00000W",
        publisher="Biblioasis",
        published="2023",
        physical_format="Trade Paperback",
    )

    result, _ = run(database, detail, {"9781771965231": gillmor})

    assert result.editions_learned == 0
    assert connection.execute("SELECT count(*) AS n FROM edition").fetchone()["n"] == 0


def test_a_number_nobody_attributed_is_still_learned(database):
    """The check can only reject on a disagreement, never on an absence."""
    _, connection = database
    connection.execute("UPDATE work SET author = 'John Williams' WHERE id = 1")
    a_copy(connection, "v1|1|0")
    connection.commit()
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert result.editions_learned == 1

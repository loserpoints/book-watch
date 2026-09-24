"""Tests for the background pass over a book's copies.

Nothing here reaches a network: `tests/conftest.py` makes that a loud failure,
and every client is a counting stub so the tests can assert *how much* was
asked rather than only what came back.
"""

import pytest

from book_watch import db, enrichment
from book_watch.ebay import declarations as declarations_module
from book_watch.ebay.declarations import Declarations
from book_watch.ebay.detail import Declared
from book_watch.ebay.errors import EbaySearchError
from book_watch.openlibrary import BudgetExhausted, OpenLibraryUnavailable, resolution
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
    # A copy exists because a sweep found it. Enrichment only re-asks about
    # copies in the newest sweep, so a fixture that skipped this would be
    # testing a state that cannot occur.
    connection.execute(
        "INSERT OR REPLACE INTO copy_seen (item_id, work_id, scope, sweep_id) "
        "VALUES (?, 1, 'us', ?)",
        (item_id, _a_sweep(connection)),
    )
    connection.commit()


def _a_sweep(connection, scope="us"):
    row = connection.execute(
        "SELECT id FROM sweep WHERE work_id = 1 AND scope = ? ORDER BY id DESC LIMIT 1",
        (scope,),
    ).fetchone()
    if row:
        return row["id"]
    return connection.execute(
        "INSERT INTO sweep (work_id, scope, asked_for, total_matching) "
        "VALUES (1, ?, 50, 0) RETURNING id",
        (scope,),
    ).fetchone()["id"]


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
        self.recaptured = []

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

    def outdated(self, isbns):
        """Mirrors the real resolver: rows stamped below the current capture."""
        if not isbns:
            return []
        placeholders = ",".join("?" * len(isbns))
        rows = self._connection.execute(
            f"SELECT isbn FROM openlibrary_edition WHERE isbn IN ({placeholders}) "
            "AND captured_by < ?",
            [*isbns, resolution.CAPTURE],
        )
        behind = {row["isbn"] for row in rows}
        return [isbn for isbn in isbns if isbn in behind]

    def recapture(self, isbn):
        self.recaptured.append(isbn)
        found = self.identify(isbn)
        self._connection.execute(
            "UPDATE openlibrary_edition SET captured_by = ? WHERE isbn = ?",
            (resolution.CAPTURE, isbn),
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


# --- capture versions --------------------------------------------------------


def captured_long_ago(connection, item_id=None, isbn=None):
    """Pretend a row was written by code that read less than this code does."""
    if item_id is not None:
        connection.execute(
            "UPDATE listing_declaration SET captured_by = 0 WHERE item_id = ?",
            (item_id,),
        )
    if isbn is not None:
        connection.execute(
            "UPDATE openlibrary_edition SET captured_by = 0 WHERE isbn = ?", (isbn,)
        )
    connection.commit()


def declaration(connection, item_id):
    return connection.execute(
        "SELECT * FROM listing_declaration WHERE item_id = ?", (item_id,)
    ).fetchone()


def test_a_row_at_the_current_capture_is_never_re_asked(database):
    """Nothing is stale on the day this ships, so nothing is spent."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    run(database, detail, {"9781590171998": STONER})
    before = list(detail.asked)

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert detail.asked == before
    assert result.recaptured == 0
    assert result.stale_remaining == 0


def test_a_stale_declaration_on_a_live_listing_is_replaced(database):
    """A seller is the authority on their own listing, edits included."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, item_id="v1|1|0")

    detail.answers["v1|1|0"] = Declared(
        "v1|1|0", isbn="9781590171998", author="John Williams"
    )
    result, _ = run(database, detail, {"9781590171998": STONER})

    assert result.recaptured == 1
    assert declaration(connection, "v1|1|0")["author"] == "John Williams"
    assert result.stale_remaining == 0


def test_a_seller_clearing_a_field_on_a_live_listing_clears_ours(database):
    """The other half of the same rule, and the reason it is not "keep the
    non-null one": a live seller removing a value is telling us something."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail(
        {"v1|1|0": Declared("v1|1|0", isbn="9781590171998", author="J. Williams")}
    )
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, item_id="v1|1|0")

    detail.answers["v1|1|0"] = Declared("v1|1|0", isbn="9781590171998")
    run(database, detail, {"9781590171998": STONER})

    assert declaration(connection, "v1|1|0")["author"] is None


def test_an_ended_listing_keeps_everything_it_declared(database):
    """The case that makes this a merge rather than an overwrite.

    eBay answers 404 for a listing that has gone, and copies are kept for
    ever now, so this is ordinary rather than rare. Letting that emptiness
    overwrite a good record would lose data quietly, for exactly the rows
    most likely to be re-asked about.
    """
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail(
        {"v1|1|0": Declared("v1|1|0", isbn="9781590171998", author="John Williams")}
    )
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, item_id="v1|1|0")

    detail.answers["v1|1|0"] = Declared("v1|1|0", present=False)
    result, _ = run(database, detail, {"9781590171998": STONER})

    kept = declaration(connection, "v1|1|0")
    assert kept["author"] == "John Williams"
    assert kept["isbn"] == "9781590171998"
    # Asked, at this version, and there is nothing further to learn.
    assert kept["captured_by"] == declarations_module.CAPTURE
    assert result.stale_remaining == 0


def test_a_copy_that_is_no_longer_on_sale_is_not_re_asked_about(database):
    """Its answer cannot change what the page shows, and since S16 there are
    more of these than live ones. Stale and still useful beats spent."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, item_id="v1|1|0")
    # A later sweep, in the same scope, that did not include this copy.
    connection.execute(
        "INSERT INTO sweep (work_id, scope, asked_for, total_matching) "
        "VALUES (1, 'us', 50, 0)"
    )
    connection.commit()
    asked_before = len(detail.asked)

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert len(detail.asked) == asked_before
    assert result.recaptured == 0


def test_a_stale_number_is_asked_about_again(database):
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, isbn="9781590171998")

    result, resolver = run(database, detail, {"9781590171998": STONER})

    assert resolver.recaptured == ["9781590171998"]
    assert result.stale_remaining == 0


def test_what_is_left_stale_is_reported_when_a_pass_stops_early(database):
    """The price of a rule change, visible before it is spent."""
    _, connection = database
    a_copy(connection, "v1|1|0")
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    run(database, detail, {"9781590171998": STONER})
    captured_long_ago(connection, item_id="v1|1|0")
    detail.fail_after = len(detail.asked)

    result, _ = run(database, detail, {"9781590171998": STONER})

    assert result.stopped_because == "ebay unavailable"
    assert result.stale_remaining == 1


def test_the_capture_versions_are_pinned():
    """Bumping one has to be a deliberate, visible edit.

    Forgetting is the failure mode this whole slice exists for, so the
    constants are pinned rather than left to be changed silently alongside
    the code that reads a new field.
    """
    assert declarations_module.CAPTURE == 1
    assert resolution.CAPTURE == 1

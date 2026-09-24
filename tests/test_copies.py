"""Tests for the copies a book has, and for working out which numbers are it.

The edition set used to be a table a pass wrote conclusions into. It is now
derived on read from things we observed — what sellers declared, what the
catalogue says those numbers are, who sellers say wrote them.

That is the difference between a rule change reaching every book on the list
and reaching only the next one added, so most of this file is about what a
change to the rules would do to books that already exist.
"""

from decimal import Decimal

import pytest

from book_watch import copies, db, wantlist
from book_watch.ebay.search import Listing, Money, Results

STONER = ("9781590171998", "Stoner", "John Williams")
OMNIBUS = ("9781598537024", "John Williams : Collected Novels", "John Williams")
GILLMOR = ("9781771965231", "Breaking and Entering", "Don Gillmor")
JOY = ("9780394757735", "Breaking and entering", "Joy Williams")


@pytest.fixture
def database(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


def a_book(connection, title, author):
    return wantlist.add_identified(connection, title=title, author=author)


def a_copy_declaring(connection, work_id, item_id, declared, *, epid=None, title=None):
    """One copy for sale, and everything observed about it."""
    isbn, catalogue_title, declared_author = declared
    connection.execute(
        "INSERT INTO copy (item_id, work_id, title, url, price, currency, epid) "
        "VALUES (?, ?, ?, 'https://ebay/x', '9.99', 'USD', ?)",
        (item_id, work_id, title or catalogue_title, epid),
    )
    connection.execute(
        "INSERT OR IGNORE INTO listing_declaration (item_id, isbn, author) "
        "VALUES (?, ?, ?)",
        (item_id, isbn, declared_author),
    )
    connection.execute(
        "INSERT OR IGNORE INTO openlibrary_edition (isbn, found, title) "
        "VALUES (?, 1, ?)",
        (isbn, catalogue_title),
    )
    # A real copy only exists because a sweep found it, and the page shows the
    # newest sweep of a scope. Registering that here keeps these fixtures
    # honest rather than relying on a query that happened to match orphans.
    sweep = connection.execute(
        "SELECT id FROM sweep WHERE work_id = ? AND scope = 'us' "
        "ORDER BY id DESC LIMIT 1",
        (work_id,),
    ).fetchone()
    sweep_id = (
        sweep["id"]
        if sweep
        else connection.execute(
            "INSERT INTO sweep (work_id, scope, asked_for, total_matching) "
            "VALUES (?, 'us', 50, 0) RETURNING id",
            (work_id,),
        ).fetchone()["id"]
    )
    connection.execute(
        "INSERT OR REPLACE INTO copy_seen (item_id, work_id, scope, sweep_id) "
        "VALUES (?, ?, 'us', ?)",
        (item_id, work_id, sweep_id),
    )
    connection.commit()


def tiers(connection, entry):
    return {copy.item_id: copy.tier for copy in copies.for_entry(connection, entry)}


# --- which numbers count as this book ---------------------------------------


def test_a_number_the_catalogue_calls_this_book_counts(database):
    book = a_book(database, "Stoner", "John Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", STONER)

    assert tiers(database, book)["v1|1|0"] == "certain"


def test_a_number_naming_a_different_book_does_not(database):
    """The omnibus. Its title contains the book's and its author is right."""
    book = a_book(database, "Stoner", "John Williams")
    a_copy_declaring(
        database, book.work_id, "v1|1|0", OMNIBUS, title="Stoner and two others"
    )

    assert tiers(database, book)["v1|1|0"] == "excluded"


def test_a_number_a_seller_attributes_to_someone_else_does_not(database):
    """Three different books are called *Breaking and Entering*."""
    book = a_book(database, "Breaking and Entering", "Joy Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", GILLMOR)

    assert tiers(database, book)["v1|1|0"] == "excluded"


def test_a_number_nobody_attributed_still_counts(database):
    """The check can only reject on a disagreement, never on an absence."""
    book = a_book(database, "Stoner", "John Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", (*STONER[:2], None))

    assert tiers(database, book)["v1|1|0"] == "certain"


def test_one_copy_teaches_the_others(database):
    """The point of a set: a number learned from one listing settles the next.

    Nothing is stored to make that happen — both are judged from the same
    observations on the same page view.
    """
    book = a_book(database, "Breaking and Entering", "Joy Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", JOY)
    a_copy_declaring(
        database, book.work_id, "v1|2|0", JOY, epid="12345", title="Breaking & Entering"
    )

    assert tiers(database, book)["v1|2|0"] == "certain"


# --- the reason this is derived rather than stored ---------------------------


def test_a_rule_change_re_judges_a_book_that_already_exists(database, monkeypatch):
    """The whole milestone, as one test.

    A book is set up under rules that accept a number. The rules then change
    to reject it. Nothing is migrated, nothing is re-fetched, no pass is run —
    and the next read gets the new answer.
    """
    book = a_book(database, "Breaking and Entering", "Joy Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", GILLMOR)

    monkeypatch.setattr(copies, "is_this_book", lambda *_: True)
    assert tiers(database, book)["v1|1|0"] == "certain"

    monkeypatch.undo()
    assert tiers(database, book)["v1|1|0"] == "excluded"


def test_what_somebody_typed_is_never_re_judged(database):
    """A conclusion can be withdrawn. A person's input cannot be overruled."""
    book = wantlist.add(database, "9781771965231", "Breaking and Entering")
    a_copy_declaring(database, book.work_id, "v1|1|0", GILLMOR)

    assert tiers(database, book)["v1|1|0"] == "certain"


def test_deriving_asks_nobody_anything(database):
    """Every input is something already stored, which is why a rule change is
    free rather than a re-fetch. `tests/conftest.py` makes a real request a
    loud failure, so this asserts by not exploding."""
    book = a_book(database, "Stoner", "John Williams")
    for n, declared in enumerate((STONER, OMNIBUS, GILLMOR)):
        a_copy_declaring(database, book.work_id, f"v1|{n}|0", declared)

    assert len(copies.for_entry(database, book)) == 3


# --- what a sweep keeps ------------------------------------------------------


def a_listing(item_id="v1|1|0", price="9.99", *, shipping=None, condition="Good"):
    return Listing(
        item_id=item_id,
        title="Stoner by John Williams",
        price=Money(Decimal(price), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        condition=condition,
        seller="aseller",
        shipping_cost=Money(Decimal(shipping), "USD") if shipping else None,
        thumbnail_url=None,
        listing_date=None,
    )


def on_sale(connection, entry, *, scope="us"):
    return {copy.item_id for copy in copies.for_entry(connection, entry, scope=scope)}


def swept(connection, work_id, listings, *, total=None, asked_for=50, scope="us"):
    """A sweep that knows how much it saw.

    `total` defaults to what came back, which is the ordinary case: a book with
    fewer listings than we asked for, where we genuinely saw all of them. Pass
    a bigger number for a book whose results eBay truncated.
    """
    found = Results(list(listings), len(listings) if total is None else total)
    return copies.store(connection, work_id, found, asked_for=asked_for, scope=scope)


def test_a_copy_seen_again_keeps_what_it_was(database):
    """The whole point of the slice: a refresh stops destroying the record."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing(price="9.99")])
    swept(database, book.work_id, [a_listing(price="7.50")])
    database.commit()

    history = copies.price_history(database, book.work_id, "v1|1|0")

    assert [str(price.amount) for _, price, _ in history] == ["9.99", "7.50"]


def test_an_unchanged_price_is_not_written_twice(database):
    """Only changes are logged. The same fact recorded daily forever answers
    nothing extra and is what makes the table grow without bound."""
    book = a_book(database, "Stoner", "John Williams")
    for _ in range(5):
        swept(database, book.work_id, [a_listing(price="9.99")])
    database.commit()

    assert len(copies.price_history(database, book.work_id, "v1|1|0")) == 1


def test_a_copy_that_comes_back_is_recorded_even_at_the_same_price(database):
    """Without this row, a gap with the same price either side would read as
    one continuous offer, which is not something we observed.

    The sweeps here saw the whole market, which is what makes the absence
    meaningful. The truncated case is the test below."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing()])
    swept(database, book.work_id, [])
    swept(database, book.work_id, [a_listing()])
    database.commit()

    assert len(copies.price_history(database, book.work_id, "v1|1|0")) == 2


def test_a_copy_that_stops_appearing_is_kept_but_not_shown(database):
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing("v1|1|0"), a_listing("v1|2|0")])
    swept(database, book.work_id, [a_listing("v1|1|0")])
    database.commit()

    assert on_sale(database, book) == {"v1|1|0"}
    kept = database.execute("SELECT COUNT(*) FROM copy").fetchone()[0]
    assert kept == 2


def test_when_a_vanished_copy_was_last_seen_survives(database):
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing("v1|2|0")])
    swept(database, book.work_id, [])
    database.commit()

    row = database.execute(
        "SELECT first_seen_at, last_seen_at FROM copy WHERE item_id = 'v1|2|0'"
    ).fetchone()
    assert row["last_seen_at"] is not None
    assert row["first_seen_at"] == row["last_seen_at"]


def test_shipping_changing_is_a_price_change(database):
    """What a copy costs is what it costs delivered, so this counts."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing(shipping="3.99")])
    swept(database, book.work_id, [a_listing(shipping="0.00")])
    database.commit()

    history = copies.price_history(database, book.work_id, "v1|1|0")
    assert [str(ship.amount) for _, _, ship in history] == ["3.99", "0.00"]


def test_two_sweeps_in_the_same_second_are_different_sweeps(database):
    """Why a sweep is an id and not a timestamp. A test that compared times
    would pass here by accident and fail in production."""
    book = a_book(database, "Stoner", "John Williams")
    first = swept(database, book.work_id, [a_listing("v1|1|0")])
    second = swept(database, book.work_id, [a_listing("v1|2|0")])
    database.commit()

    assert first != second
    assert on_sale(database, book) == {"v1|2|0"}


def test_a_copy_missing_from_a_truncated_sweep_has_not_come_back(database):
    """We ask for a fixed number and eBay ranks by relevance, so a copy at the
    edge falls in and out of the results while sitting untouched. Calling that
    a reappearance would fill the history with rows describing eBay's ranking
    rather than the market."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing()], total=400)
    swept(database, book.work_id, [], total=400)
    swept(database, book.work_id, [a_listing()], total=400)
    database.commit()

    assert len(copies.price_history(database, book.work_id, "v1|1|0")) == 1


def test_a_sweep_records_what_it_asked_for_and_what_matched(database):
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing()], total=400, asked_for=50)
    database.commit()

    row = database.execute("SELECT asked_for, total_matching FROM sweep").fetchone()
    assert (row["asked_for"], row["total_matching"]) == (50, 400)


# --- where a copy is ---------------------------------------------------------


def abroad(item_id="v1|9|0", country="GB"):
    return Listing(
        item_id=item_id,
        title="State of Grace (UK IMPORT)",
        price=Money(Decimal("21.06"), "USD"),
        item_web_url="https://www.ebay.com/itm/9",
        condition="Brand New",
        seller="rarewaves",
        shipping_cost=Money(Decimal("0.00"), "USD"),
        thumbnail_url=None,
        listing_date=None,
        located_in=country,
    )


def test_a_us_sweep_does_not_bury_what_an_everywhere_sweep_found(database):
    """The reason a sweep records its scope.

    A copy absent from the newest sweep is no longer shown, and that only
    holds while consecutive sweeps ask eBay the same question. Without the
    scope, the first US-only sweep after an everywhere sweep would bury every
    overseas copy — and they went nowhere, we stopped asking.
    """
    book = a_book(database, "State of grace", "Joy Williams")
    swept(database, book.work_id, [a_listing(), abroad()], scope="everywhere")
    swept(database, book.work_id, [a_listing()], scope="us")
    database.commit()

    assert on_sale(database, book, scope="us") == {"v1|1|0"}
    assert on_sale(database, book, scope="everywhere") == {"v1|1|0", "v1|9|0"}


def test_a_copy_vanishing_within_one_scope_still_stops_being_shown(database):
    """Scope must not become an excuse that keeps sold copies on the page."""
    book = a_book(database, "State of grace", "Joy Williams")
    swept(database, book.work_id, [a_listing(), abroad()], scope="everywhere")
    swept(database, book.work_id, [a_listing()], scope="everywhere")
    database.commit()

    assert on_sale(database, book, scope="everywhere") == {"v1|1|0"}


def test_where_a_copy_is_comes_back_out(database):
    book = a_book(database, "State of grace", "Joy Williams")
    swept(database, book.work_id, [abroad()], scope="everywhere")
    database.commit()

    (copy,) = copies.for_entry(database, book, scope="everywhere")
    assert copy.located_in == "GB"


def test_an_unstated_country_is_not_treated_as_abroad(database):
    book = a_book(database, "State of grace", "Joy Williams")
    swept(database, book.work_id, [abroad(country=None)], scope="everywhere")
    database.commit()

    (copy,) = copies.for_entry(database, book, scope="everywhere")
    assert copy.located_in is None


def test_the_gate_is_per_scope(database):
    """A recent US sweep must not block a first look at everything."""
    book = a_book(database, "State of grace", "Joy Williams")
    swept(database, book.work_id, [a_listing()], scope="us")
    database.commit()

    assert not copies.due_for_sweep(database, book.work_id, scope="us")
    assert copies.due_for_sweep(database, book.work_id, scope="everywhere")

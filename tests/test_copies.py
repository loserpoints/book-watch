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

from book_watch import copies, db, standing, sweeps, wantlist
from book_watch.copies import Copy
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


def a_listing(
    item_id="v1|1|0",
    price="9.99",
    *,
    shipping=None,
    condition="Good",
    condition_id=None,
):
    return Listing(
        item_id=item_id,
        title="Stoner by John Williams",
        price=Money(Decimal(price), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        condition=condition,
        condition_id=condition_id,
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
    return sweeps.store(connection, work_id, found, asked_for=asked_for, scope=scope)


def test_a_copy_seen_again_keeps_what_it_was(database):
    """The whole point of the slice: a refresh stops destroying the record."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing(price="9.99")])
    swept(database, book.work_id, [a_listing(price="7.50")])
    database.commit()

    history = sweeps.price_history(database, book.work_id, "v1|1|0")

    assert [str(price.amount) for _, price, _ in history] == ["9.99", "7.50"]


def test_an_unchanged_price_is_not_written_twice(database):
    """Only changes are logged. The same fact recorded daily forever answers
    nothing extra and is what makes the table grow without bound."""
    book = a_book(database, "Stoner", "John Williams")
    for _ in range(5):
        swept(database, book.work_id, [a_listing(price="9.99")])
    database.commit()

    assert len(sweeps.price_history(database, book.work_id, "v1|1|0")) == 1


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

    assert len(sweeps.price_history(database, book.work_id, "v1|1|0")) == 2


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

    history = sweeps.price_history(database, book.work_id, "v1|1|0")
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

    assert len(sweeps.price_history(database, book.work_id, "v1|1|0")) == 1


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

    assert not sweeps.due_for_sweep(database, book.work_id, scope="us")
    assert sweeps.due_for_sweep(database, book.work_id, scope="everywhere")


# --- what I will pay ---------------------------------------------------------


def priced(price, shipping, currency="USD"):
    return Copy(
        item_id="v1|1|0",
        title="Stoner",
        url="https://ebay/x",
        price=Money(Decimal(price), currency),
        shipping=Money(Decimal(shipping), currency) if shipping is not None else None,
        tier="certain",
    )


EIGHT = Money(Decimal("8.00"), "USD")


def test_a_cheap_copy_with_cheap_postage_is_under():
    assert priced("5.00", "2.00").against(EIGHT) == "under"


def test_landed_cost_is_what_counts_not_the_price():
    """$7 plus $3 postage is not a $7 copy. Shipping is the difference between
    a good copy and a bad deal, which is why the ceiling is a delivered one."""
    assert priced("7.00", "3.00").against(EIGHT) == "over"


def test_exactly_at_the_ceiling_is_under():
    """A limit somebody typed is what they will pay, not what they will
    exceed. Rejecting the copy that costs exactly it would be pedantry."""
    assert priced("8.00", "0.00").against(EIGHT) == "under"


def test_unstated_shipping_cannot_be_judged():
    """Not under, and not over. Calling it free would invent a bargain, which
    is the wasted-trust failure the brief exists to avoid; calling it over
    would be right most of the time with no way to know which times."""
    assert priced("5.00", None).against(EIGHT) == "shipping unstated"


def test_another_currency_cannot_be_judged():
    assert priced("5.00", "2.00", currency="GBP").against(EIGHT) == "another currency"


def test_without_a_ceiling_nothing_is_judged():
    assert priced("5.00", "2.00").against(None) == "no ceiling"


def test_a_ceiling_never_hides_or_reorders_anything(database):
    """The ceiling annotates. Decision 33 chose grading over filtering because
    a copy just over the line is exactly the one worth seeing."""
    book = a_book(database, "Stoner", "John Williams")
    swept(
        database,
        book.work_id,
        [
            a_listing("v1|1|0", price="30.00", shipping="0.00"),
            a_listing("v1|2|0", price="4.00", shipping="1.00"),
        ],
    )
    database.commit()
    before = [copy.item_id for copy in copies.for_entry(database, book)]

    # Re-read the entry: `for_entry` is given one, so testing with the copy
    # fetched before the ceiling existed would prove nothing.
    book = wantlist.set_ceiling(database, book.id, "8.00", "USD")
    assert book.will_pay is not None
    after = copies.for_entry(database, book)

    assert [copy.item_id for copy in after] == before
    assert {c.item_id: c.against(Money(Decimal("8.00"), "USD")) for c in after} == {
        "v1|1|0": "over",
        "v1|2|0": "under",
    }


# --- where this copy sits among the others -----------------------------------
#
# Two populations, and keeping them apart is most of what these assert. A rank
# counts what is listed *now*, because you cannot be cheapest of a set
# including four copies that are gone. A range spans every copy ever seen,
# because a copy that has left was still a real book at a real price.


USED, LIKE_NEW, BRAND_NEW = "5000", "2750", "1000"


def a_certain_copy(
    connection,
    work_id,
    item_id,
    *,
    price="10.00",
    shipping="0.00",
    condition_id=USED,
    currency="USD",
    listed=True,
    declared=STONER,
    condition=None,
):
    """A copy that grades `certain`, priced and graded as a seller would.

    `listed=False` is a copy that has stopped appearing: still recorded, still
    part of what this book has been seen at, no longer something you can buy.
    """
    a_copy_declaring(connection, work_id, item_id, declared)
    connection.execute(
        "UPDATE copy SET price = ?, shipping = ?, currency = ?, "
        "       condition_id = ?, condition = ? "
        " WHERE item_id = ? AND work_id = ?",
        (price, shipping, currency, condition_id, condition, item_id, work_id),
    )
    if not listed:
        connection.execute(
            "DELETE FROM copy_seen WHERE item_id = ? AND work_id = ?",
            (item_id, work_id),
        )
    connection.commit()


def standing_for(connection, entry):
    return standing.standings(
        copies.for_entry(connection, entry), copies.ever_seen(connection, entry)
    )


def test_a_new_copy_does_not_move_a_used_copys_rank(database):
    """The heart of the slice. New and used are two markets, not two grades on
    one scale: a new copy is priced by distributor economics through bulk
    sellers and a used one by scarcity and wear. Pooling them would put a
    floor under the used number that has nothing to do with the used market —
    and would make an ordinary used copy look like a find."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="24.00")
    a_certain_copy(
        database, book.work_id, "v1|3|0", price="4.00", condition_id=BRAND_NEW
    )

    stands = standing_for(database, book)

    # The $4 new copy is cheaper than both used copies and changes neither.
    assert (stands["v1|1|0"].rank, stands["v1|1|0"].listed) == (1, 2)
    assert (stands["v1|2|0"].rank, stands["v1|2|0"].listed) == (2, 2)
    assert (stands["v1|3|0"].rank, stands["v1|3|0"].listed) == (1, 1)
    assert stands["v1|1|0"].condition_class == "used"
    assert stands["v1|3|0"].condition_class == "new"


def test_the_range_never_reaches_across_the_two_markets(database):
    """The same split, applied to the range rather than the rank."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="36.00")
    a_certain_copy(
        database, book.work_id, "v1|3|0", price="4.00", condition_id=BRAND_NEW
    )

    used = standing_for(database, book)["v1|1|0"]

    assert (used.low.amount, used.high.amount) == (Decimal("18.00"), Decimal("36.00"))
    assert used.seen == 2


def test_like_new_is_still_a_used_copy(database):
    """It has had an owner, which is the thing that separates the markets.
    'Like New' is a grade within secondhand, not a second kind of new."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(
        database, book.work_id, "v1|2|0", price="24.00", condition_id=LIKE_NEW
    )

    stands = standing_for(database, book)

    assert stands["v1|2|0"].condition_class == "used"
    assert stands["v1|1|0"].listed == 2


def test_the_class_comes_from_the_id_and_never_from_the_words(database):
    """Decision 33 lost seven listings to trusting eBay's category strings.
    The display string is localized and re-worded; the number is not. So a
    copy whose words say one thing and whose id says another follows the id."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(
        database, book.work_id, "v1|1|0", condition_id=USED, condition="Brand New"
    )

    assert standing_for(database, book)["v1|1|0"].condition_class == "used"


def test_a_copy_alone_in_its_class_says_so_rather_than_ranking(database):
    """ "Cheapest of 1" is a true sentence that tells you nothing and sounds
    like it told you something."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")

    alone = standing_for(database, book)["v1|1|0"]

    assert (alone.rank, alone.listed) == (1, 1)


def test_the_range_spans_copies_that_are_no_longer_listed(database):
    """A copy that has gone still happened. Dropping it would leave the range
    describing only what has *not* sold — the slowest-moving and most
    over-priced end of the market."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="30.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="12.00", listed=False)

    here = standing_for(database, book)["v1|1|0"]

    # Alone on the shelf, but not alone in the record.
    assert here.listed == 1
    assert here.seen == 2
    assert (here.low.amount, here.high.amount) == (Decimal("12.00"), Decimal("30.00"))


def test_a_vanished_copy_gets_no_standing_of_its_own(database):
    """It is part of the range and absent from the page. Nothing to place."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="30.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="12.00", listed=False)

    assert "v1|2|0" not in standing_for(database, book)


def test_rank_is_on_the_delivered_price_not_the_asking_one(database):
    """Price and postage are one number here. A seller who moves cost from the
    price into the postage must not be able to move their copy up the page by
    doing it — that is the whole reason the ceiling is delivered too."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "cheap|ask", price="7.00", shipping="6.00")
    a_certain_copy(database, book.work_id, "cheap|real", price="10.00", shipping="0.00")

    stands = standing_for(database, book)

    assert stands["cheap|real"].rank == 1
    assert stands["cheap|ask"].rank == 2


def test_a_ceiling_does_not_change_where_a_copy_ranks(database):
    """A rank is about the market; a ceiling is about you. A copy over your
    limit is still one of the copies the cheaper ones are cheaper *than*."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="4.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="40.00")

    without = standing_for(database, book)["v1|1|0"]
    wantlist.set_ceiling(database, book.id, "10.00", "USD")
    database.commit()
    with_limit = standing_for(database, wantlist.get(database, book.id))["v1|1|0"]

    assert (with_limit.rank, with_limit.listed) == (without.rank, without.listed)
    assert with_limit.listed == 2


def test_a_copy_with_no_stated_condition_is_not_ranked(database):
    """Its own class of one, which means it mostly says nothing — the honest
    outcome. Two copies that might each be shrink-wrapped or water-damaged are
    not evidence about one another."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", condition_id=None)
    a_certain_copy(database, book.work_id, "v1|2|0", condition_id=None)

    stands = standing_for(database, book)

    assert stands["v1|1|0"].unplaced == "condition unstated"
    assert stands["v1|1|0"].rank is None


def test_words_without_a_code_are_a_different_silence(database):
    """A copy can carry eBay's words without eBay's number — every row
    recorded before the code was kept does. That is not the seller staying
    quiet, and the page must not say it was."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(
        database, book.work_id, "v1|1|0", condition_id=None, condition="Good"
    )

    assert standing_for(database, book)["v1|1|0"].unplaced == "no condition code"


def test_an_unstated_condition_does_not_enter_anyone_elses_range(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="24.00")
    a_certain_copy(database, book.work_id, "v1|3|0", price="99.00", condition_id=None)

    used = standing_for(database, book)["v1|1|0"]

    assert used.seen == 2
    assert used.high.amount == Decimal("24.00")


def test_a_copy_without_a_delivered_price_cannot_be_placed(database):
    """Same refusal the ceiling makes. Unstated postage is not free and not
    infinite, and a rank built on either guess is a claim rather than a sort."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00", shipping=None)
    a_certain_copy(database, book.work_id, "v1|2|0", price="24.00")

    stands = standing_for(database, book)

    assert stands["v1|1|0"].unplaced == "no delivered price"
    assert stands["v1|1|0"].rank is None
    # And it is absent from the population it could not join.
    assert stands["v1|2|0"].listed == 1
    assert stands["v1|2|0"].seen == 1


def test_currencies_do_not_pool(database):
    """A range from £5 to $36 is not a range, and a symbol would not make it
    one. Decision 50 refuses the same comparison for the ceiling."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="5.00", currency="GBP")

    stands = standing_for(database, book)

    assert stands["v1|1|0"].listed == 1
    assert stands["v1|1|0"].seen == 1
    assert stands["v1|2|0"].listed == 1


def test_two_copies_at_the_same_price_are_both_cheapest(database):
    """Handing one of them first place because it sorted higher would be a
    coin toss presented as a finding."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="9.99")
    a_certain_copy(database, book.work_id, "v1|2|0", price="9.99")
    a_certain_copy(database, book.work_id, "v1|3|0", price="20.00")

    stands = standing_for(database, book)

    assert (stands["v1|1|0"].rank, stands["v1|1|0"].tied) == (1, True)
    assert (stands["v1|2|0"].rank, stands["v1|2|0"].tied) == (1, True)
    # Competition ranking: the next one along is third, not second.
    assert (stands["v1|3|0"].rank, stands["v1|3|0"].tied) == (3, False)


def test_only_copies_that_are_certainly_this_book_are_compared(database):
    """The possible tier ran at 8–14% precision on the edition question, so a
    range across it would mostly be other books and a rank against it would be
    a rank against a different title."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="24.00")
    # Declares a number the catalogue calls a different book entirely.
    a_certain_copy(database, book.work_id, "v1|3|0", price="1.00", declared=GILLMOR)

    stands = standing_for(database, book)

    assert "v1|3|0" not in stands
    assert stands["v1|1|0"].rank == 1
    assert stands["v1|1|0"].listed == 2


def test_the_condition_id_survives_a_sweep(database):
    """It has arrived in every search response since the client was written
    and been dropped one line later."""
    book = a_book(database, "Stoner", "John Williams")
    swept(database, book.work_id, [a_listing(condition="Good", condition_id=USED)])
    database.commit()

    stored = database.execute(
        "SELECT condition_id FROM copy WHERE item_id = 'v1|1|0'"
    ).fetchone()
    assert stored["condition_id"] == USED


def test_a_copy_recorded_before_the_id_was_stored_reads_as_unknown(database):
    """Existing rows are not backfilled from the display string — that is the
    exact thing the column exists to stop trusting. Unknown is the truth."""
    book = a_book(database, "Stoner", "John Williams")
    a_copy_declaring(database, book.work_id, "v1|1|0", STONER)

    only = copies.for_entry(database, book)[0]

    assert only.condition_id is None
    assert only.condition_class == "unknown"


# --- the markets a book sits in ----------------------------------------------
#
# The same numbers as a standing, lifted from the copy to the book. What these
# guard is mostly what is *absent*: a class with nothing listed, the unknown
# class, and a range that is really one number.


def markets_for(connection, entry):
    return standing.markets(standing_for(connection, entry))


def test_used_comes_before_new(database):
    """The reading hunt is the dominant one and a new copy is usually bulk
    inventory. *Two kinds of hunt* may invert this for collectible entries,
    which is why the order lives in one place rather than in a template."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(
        database, book.work_id, "v1|1|0", price="4.00", condition_id=BRAND_NEW
    )
    a_certain_copy(database, book.work_id, "v1|2|0", price="18.00")

    assert [m.condition_class for m in markets_for(database, book)] == ["used", "new"]


def test_a_market_counts_listed_copies_and_spans_seen_ones(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="24.00")
    a_certain_copy(database, book.work_id, "v1|3|0", price="36.00", listed=False)

    (used,) = markets_for(database, book)

    assert (used.listed, used.seen) == (2, 3)
    assert (used.low.amount, used.high.amount) == (Decimal("18.00"), Decimal("36.00"))


def test_the_unknown_class_is_never_a_market(database):
    """It has no range worth stating and no rank to head, so the page mentions
    it only on the copies themselves, where it says why it could not be
    placed."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", condition_id=None)

    assert markets_for(database, book) == []


def test_a_class_whose_copies_have_all_gone_heads_nothing(database):
    """These head a list. A class with nothing in that list has no list to
    head — its range is a real fact and a different statement from this one."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00", listed=False)
    a_certain_copy(
        database, book.work_id, "v1|2|0", price="4.00", condition_id=BRAND_NEW
    )

    assert [m.condition_class for m in markets_for(database, book)] == ["new"]


def test_one_copy_is_not_a_range(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")

    (used,) = markets_for(database, book)

    assert used.listed == 1
    assert used.has_range is False


def test_two_copies_at_one_price_are_not_a_range_either(database):
    """ "Asking 18.00–18.00" is a sentence that looks like information."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="18.00")

    (used,) = markets_for(database, book)

    assert used.seen == 2
    assert used.has_range is False


def test_currencies_are_separate_markets(database):
    """Decision 50's refusal, applied to a range: £5 to $36 is not a range and
    a symbol would not make it one."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="5.00", currency="GBP")

    markets = markets_for(database, book)

    assert len(markets) == 2
    assert {m.low.currency for m in markets} == {"USD", "GBP"}
    assert all(m.listed == 1 for m in markets)


def test_a_copy_that_cannot_be_placed_makes_no_market(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00", shipping=None)

    assert markets_for(database, book) == []


# --- what the want-list leads with -------------------------------------------


def glance_at(connection, entry):
    return standing.glance(connection, entry)


def test_the_headline_leads_with_the_cheapest_used_copy(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(database, book.work_id, "v1|2|0", price="9.00", shipping="3.00")

    lead = glance_at(database, book).headline

    assert lead.market.condition_class == "used"
    assert lead.cheapest.amount == Decimal("12.00")


def test_a_book_with_no_used_copies_falls_back_to_the_new_market(database):
    """*State of Grace* is five copies, all Brand New. "Nothing listed" would
    be false, and showing nothing would be worse than showing the new price
    as long as it says which market it came from."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(
        database, book.work_id, "v1|1|0", price="21.00", condition_id=BRAND_NEW
    )
    a_certain_copy(
        database, book.work_id, "v1|2|0", price="36.00", condition_id=BRAND_NEW
    )

    lead = glance_at(database, book).headline

    assert lead.market.condition_class == "new"
    assert lead.cheapest.amount == Decimal("21.00")


def test_one_used_copy_beats_a_cheaper_new_one_for_the_headline(database):
    """The fallback is a fallback, not a comparison. A $4 new copy does not
    displace the used market the reading hunt is actually watching."""
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")
    a_certain_copy(
        database, book.work_id, "v1|2|0", price="4.00", condition_id=BRAND_NEW
    )

    lead = glance_at(database, book).headline

    assert lead.market.condition_class == "used"
    assert lead.cheapest.amount == Decimal("18.00")


def test_the_headline_carries_the_ceiling_verdict(database):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="10.00", shipping="1.00")
    wantlist.set_ceiling(database, book.id, "11.00", "USD")
    database.commit()

    lead = glance_at(database, wantlist.get(database, book.id)).headline

    assert lead.verdict == "under"


def test_a_book_nobody_has_checked_is_told_apart_from_an_empty_one(database):
    """Two different facts. Saying the second about the first is a confident
    claim about a market we never asked about."""
    book = a_book(database, "Stoner", "John Williams")

    never = glance_at(database, book)

    assert never.checked is None
    assert (never.listed, never.uncertain, never.headline) == (0, 0, None)


def test_uncertain_copies_are_counted_rather_than_called_nothing(database):
    """ "Nothing listed" over five copies carrying the title would be false."""
    book = a_book(database, "Stoner", "John Williams")
    # Carries the title and nothing that proves the book — no number from the
    # seller, no product the catalogue recognises. Text alone never reaches
    # certain (decision 33), so this is the "might be this book" pile.
    a_copy_declaring(database, book.work_id, "v1|1|0", STONER, title="Stoner")
    database.execute("DELETE FROM listing_declaration WHERE item_id = 'v1|1|0'")
    database.commit()

    at = glance_at(database, book)

    assert at.listed == 0
    assert at.headline is None
    assert at.uncertain == 1


def test_one_render_derives_the_edition_set_once(database, monkeypatch):
    """Both populations come from one `_target` call.

    Not a speed test — a ten-book want-list renders in about 12ms either way.
    It is that two adjacent derivations invite the question of whether they
    could disagree, and the answer should be that there is only one to ask
    about. Without this, the duplication comes back the next time somebody
    needs both populations and reaches for the two public functions.
    """
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")

    derived = []
    real = copies._target
    monkeypatch.setattr(
        copies, "_target", lambda *a, **k: (derived.append(1), real(*a, **k))[1]
    )

    listed, seen = copies.populations(database, book)

    assert len(derived) == 1
    assert [one.item_id for one in listed] == ["v1|1|0"]
    assert [one.item_id for one in seen] == ["v1|1|0"]


def test_the_glance_derives_it_once_too(database, monkeypatch):
    book = a_book(database, "Stoner", "John Williams")
    a_certain_copy(database, book.work_id, "v1|1|0", price="18.00")

    derived = []
    real = copies._target
    monkeypatch.setattr(
        copies, "_target", lambda *a, **k: (derived.append(1), real(*a, **k))[1]
    )

    standing.glance(database, book)

    assert len(derived) == 1

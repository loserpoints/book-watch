"""A listing is its marketplace and its id there, and a second marketplace
lives in the same tables as eBay without disturbing eBay's copies (S65)."""

import shutil
from decimal import Decimal

import pytest

from book_watch import copies, db, enrichment, sweeps, wantlist
from book_watch.ebay.search import Listing, Money, Results
from book_watch.marketplaces import abebooks_condition_id


@pytest.fixture
def database(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


def a_listing(item_id, price="9.99", located_in="US"):
    return Listing(
        item_id=item_id,
        title="Geronimo Rex",
        price=Money(Decimal(price), "USD"),
        item_web_url=f"https://example.com/{item_id}",
        located_in=located_in,
        shipping_cost=Money(Decimal("4.00"), "USD"),
    )


def keys(connection, entry, scope="us"):
    return {copy.key for copy in copies.for_entry(connection, entry, scope=scope)}


def test_a_sweep_of_one_marketplace_never_hides_another(database):
    entry = wantlist.add_identified(database, title="Geronimo Rex", author="Hannah")
    book = entry.work_id

    sweeps.store(database, book, Results([a_listing("v1|1|0")], total=1))
    sweeps.store(
        database,
        book,
        Results([a_listing("32473927550")], total=1),
        marketplace="abebooks",
    )

    assert keys(database, entry) == {("ebay", "v1|1|0"), ("abebooks", "32473927550")}


def test_a_later_sweep_of_the_same_marketplace_still_replaces_what_is_listed(
    database,
):
    entry = wantlist.add_identified(database, title="Geronimo Rex", author="Hannah")
    book = entry.work_id
    sweeps.store(database, book, Results([a_listing("v1|1|0")], total=1))
    sweeps.store(
        database, book, Results([a_listing("111")], total=1), marketplace="abebooks"
    )

    sweeps.store(
        database, book, Results([a_listing("222")], total=1), marketplace="abebooks"
    )

    assert keys(database, entry) == {("ebay", "v1|1|0"), ("abebooks", "222")}


def test_the_same_id_on_two_marketplaces_is_two_copies(database):
    entry = wantlist.add_identified(database, title="Geronimo Rex", author="Hannah")
    book = entry.work_id

    sweeps.store(database, book, Results([a_listing("123")], total=1))
    sweeps.store(
        database, book, Results([a_listing("123")], total=1), marketplace="abebooks"
    )

    assert keys(database, entry) == {("ebay", "123"), ("abebooks", "123")}


def test_one_mixed_search_feeds_both_views(database):
    entry = wantlist.add_identified(database, title="Geronimo Rex", author="Hannah")
    book = entry.work_id
    found = Results(
        [a_listing("1", located_in="US"), a_listing("2", located_in="GB")], total=2
    )

    sweeps.store_both_scopes(database, book, found, marketplace="abebooks")

    assert keys(database, entry, scope="everywhere") == {
        ("abebooks", "1"),
        ("abebooks", "2"),
    }
    assert keys(database, entry, scope="us") == {("abebooks", "1")}


def test_only_ebay_listings_are_ever_sent_to_ebay(database):
    entry = wantlist.add_identified(database, title="Geronimo Rex", author="Hannah")
    book = entry.work_id
    sweeps.store(database, book, Results([a_listing("v1|1|0")], total=1))
    sweeps.store(
        database, book, Results([a_listing("111")], total=1), marketplace="abebooks"
    )

    found = copies.for_entry(database, entry)

    assert copies.unasked(found) == ["v1|1|0"]
    assert enrichment._on_sale_now(database, book) == ["v1|1|0"]


@pytest.mark.parametrize(
    ("words", "code"),
    [
        ("New", "1000"),
        ("Used - As new", "2750"),
        ("Used - Fine", "2750"),
        ("Used - Near fine", "4000"),
        ("Used - Very good", "4000"),
        ("Used - Good", "5000"),
        ("Used - Fair", "6000"),
        ("Used - Poor", "6000"),
        ("Used", "3000"),
        (None, None),
    ],
)
def test_abebooks_condition_lands_on_ebays_scale(words, code):
    assert abebooks_condition_id(words) == code


def test_every_existing_listing_becomes_ebays(database, monkeypatch, tmp_path):
    """The migration keeps every row and keys it by marketplace and id."""
    before = tmp_path / "before"
    before.mkdir()
    for migration in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
        if migration.name < "025":
            shutil.copy(migration, before / migration.name)
    fresh = db.connect(tmp_path / "old.db")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", before)
    db.migrate(fresh)
    fresh.executescript(
        """
        INSERT INTO work (id, title) VALUES (1, 'Geronimo Rex');
        INSERT INTO sweep (id, work_id, scope) VALUES (1, 1, 'us');
        INSERT INTO copy (item_id, work_id, title, url, price, currency)
        VALUES ('v1|1|0', 1, 'Geronimo Rex', 'https://ebay/1', '9.99', 'USD');
        INSERT INTO copy_seen (item_id, work_id, scope, sweep_id)
        VALUES ('v1|1|0', 1, 'us', 1);
        INSERT INTO sighting (item_id, work_id, sweep_id, price, currency)
        VALUES ('v1|1|0', 1, 1, '9.99', 'USD');
        INSERT INTO emailed_copy (item_id, work_id) VALUES ('v1|1|0', 1);
        INSERT INTO listing_declaration (item_id, isbn)
        VALUES ('v1|1|0', '9780802135698');
        """
    )
    monkeypatch.undo()

    assert db.migrate(fresh)[0] == "025_which_marketplace.sql"

    for table in (
        "copy",
        "copy_seen",
        "sighting",
        "emailed_copy",
        "listing_declaration",
    ):
        rows = fresh.execute(f"SELECT marketplace, item_id FROM {table}").fetchall()
        assert [tuple(row) for row in rows] == [("ebay", "v1|1|0")], table
    sweep = fresh.execute("SELECT marketplace FROM sweep").fetchone()
    assert sweep["marketplace"] == "ebay"
    fresh.close()

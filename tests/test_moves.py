"""Which way the latest check moved a price (S72, #164)."""

from decimal import Decimal

import pytest

from book_watch import db, moves, standing, sweeps, wantlist
from book_watch.ebay.search import Listing, Money
from book_watch.web import list_view

ISBN = "9781590171998"


@pytest.fixture
def connection(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


def copy(item_id, price, shipping="0"):
    return Listing(
        item_id=item_id,
        title="Stoner by John Williams",
        price=Money(Decimal(price), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        shipping_cost=Money(Decimal(shipping), "USD") if shipping else None,
    )


def a_book(connection, limit="8"):
    entry = wantlist.add_identified(connection, title="Stoner", isbn=ISBN)
    wantlist.set_ceiling(connection, entry.id, limit, "USD")
    return entry


def certain(connection, *item_ids):
    for item_id in item_ids:
        connection.execute(
            "INSERT OR IGNORE INTO listing_declaration (item_id, isbn) VALUES (?, ?)",
            (item_id, ISBN),
        )


def check(connection, entry, listings, *, examined=True):
    """One check: earlier ones are pushed back past `SAME_CHECK`, so this one
    takes its own note, as a check the next morning would."""
    connection.execute(
        "UPDATE entry SET checked_from_at = datetime('now', '-1 day') "
        "WHERE checked_from_at IS NOT NULL"
    )
    connection.execute("UPDATE sweep SET at = datetime(at, '-1 day')")
    sweeps.store(connection, entry.work_id, listings)
    if examined:
        certain(connection, *(listing.item_id for listing in listings))


def row(connection, entry):
    entry = wantlist.get(connection, entry.id)
    return list_view.row(entry, standing.glance(connection, entry))


def test_a_cheaper_from_price_shows_down_and_says_what_it_was(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25"), copy("b", "12")])
    check(connection, entry, [copy("a", "6.49"), copy("b", "12")])

    shown = row(connection, entry)

    assert (shown["move"], shown["was_text"]) == ("down", "$8.25")


def test_the_cheapest_copy_selling_shows_up(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "9.75"), copy("b", "12.15")])
    check(connection, entry, [copy("b", "12.15")])

    assert row(connection, entry)["move"] == "up"


def test_a_check_that_leaves_the_from_price_alone_clears_the_caret(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    check(connection, entry, [copy("a", "6.49")])
    check(connection, entry, [copy("a", "6.49")])

    assert row(connection, entry)["move"] is None


def test_every_change_counts_however_small(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    check(connection, entry, [copy("a", "8.24")])

    assert row(connection, entry)["move"] == "down"


def test_nothing_before_or_no_price_now_shows_no_caret(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])

    assert row(connection, entry)["move"] is None


def test_a_copy_examined_after_the_search_counts_toward_that_check(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    check(connection, entry, [copy("a", "8.25"), copy("b", "5")], examined=False)
    assert row(connection, entry)["move"] is None

    certain(connection, "b")

    assert row(connection, entry)["move"] == "down"


def test_stores_within_one_check_share_one_note(connection):
    """eBay's search and AbeBooks' page, US and everywhere, follow each other
    within seconds: the second store must not note the first one's price."""
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    check(connection, entry, [copy("a", "6.49")])
    sweeps.store(connection, entry.work_id, [copy("a", "6.49")], marketplace="abebooks")

    assert row(connection, entry)["move"] == "down"


def test_only_a_us_store_takes_the_note(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    connection.execute("UPDATE entry SET checked_from_at = datetime('now', '-1 day')")

    sweeps.store(connection, entry.work_id, [copy("a", "8.25")], scope="everywhere")

    noted = connection.execute("SELECT checked_from_at FROM entry").fetchone()[0]
    assert noted < connection.execute("SELECT datetime('now', '-1 hour')").fetchone()[0]


def test_a_copy_the_latest_check_repriced_carries_its_own_caret(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25"), copy("b", "12"), copy("c", "14")])
    check(connection, entry, [copy("a", "6.49"), copy("b", "12.50"), copy("c", "14")])

    moved = moves.of_copies(connection, entry.work_id)

    assert moved[("ebay", "a")] == moves.Move("down", Money(Decimal("8.25"), "USD"))
    assert moved[("ebay", "b")].direction == "up"
    assert ("ebay", "c") not in moved


def test_a_copy_repriced_at_an_earlier_check_has_no_caret_now(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25")])
    check(connection, entry, [copy("a", "6.49")])
    check(connection, entry, [copy("a", "6.49")])

    assert moves.of_copies(connection, entry.work_id) == {}


def test_unknown_shipping_gets_no_caret(connection):
    entry = a_book(connection)
    check(connection, entry, [copy("a", "8.25", shipping=None)])
    check(connection, entry, [copy("a", "6.49")])

    assert moves.of_copies(connection, entry.work_id) == {}

"""Counting how copies' prices move, from the price history (S72, #164)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from book_watch import db, price_moves, sweeps, wantlist
from book_watch.ebay.search import Listing, Money


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


def a_book(connection, limit=None):
    entry = wantlist.add_identified(connection, title="Stoner", isbn="9781590171998")
    if limit:
        wantlist.set_ceiling(connection, entry.id, limit, "USD")
    return entry


def checks(connection, entry, *sweeps_of_listings):
    for listings in sweeps_of_listings:
        sweeps.store(connection, entry.work_id, listings)


def counted(connection, days=14):
    return price_moves.count(connection, datetime.now(UTC), days)


def test_moves_are_counted_each_way_and_by_size(connection):
    entry = a_book(connection)
    checks(
        connection,
        entry,
        [copy("a", "10"), copy("b", "10"), copy("c", "10")],
        [copy("a", "9.80"), copy("b", "11.50"), copy("c", "4")],
    )

    moves = counted(connection)

    assert moves.down == {"under $0.50": 1, "over $2": 1}
    assert moves.up == {"$0.50 to $2": 1}
    assert (moves.copies, moves.copies_moved, moves.books_moved) == (3, 3, 1)


def test_crossing_the_limit_is_counted_each_way(connection):
    entry = a_book(connection, limit="8")
    checks(
        connection,
        entry,
        [copy("a", "9"), copy("b", "7")],
        [copy("a", "8"), copy("b", "8.50")],
    )

    moves = counted(connection)

    assert (moves.under, moves.over) == (1, 1)


def test_a_copy_coming_back_at_the_same_price_is_not_a_move(connection):
    entry = a_book(connection)
    checks(connection, entry, [copy("a", "9")], [], [copy("a", "9")])

    moves = counted(connection)

    assert (sum(moves.down.values()), sum(moves.up.values())) == (0, 0)


def test_a_move_before_the_window_is_left_out(connection):
    entry = a_book(connection)
    checks(connection, entry, [copy("a", "10")], [copy("a", "8")])
    old = (datetime.now(UTC) - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute("UPDATE sweep SET at = ?", (old,))

    assert sum(counted(connection).down.values()) == 0


def test_unknown_shipping_is_counted_apart(connection):
    entry = a_book(connection)
    checks(connection, entry, [copy("a", "10", shipping=None)], [copy("a", "8")])

    moves = counted(connection)

    assert (sum(moves.down.values()), moves.unknown) == (0, 1)


def test_a_book_off_the_list_is_left_out(connection):
    entry = a_book(connection)
    checks(connection, entry, [copy("a", "10")], [copy("a", "8")])
    wantlist.remove(connection, entry.id)

    moves = counted(connection)

    assert (moves.books, sum(moves.down.values())) == (0, 0)


def test_it_prints_counts_and_nothing_of_the_books(
    connection, tmp_path, monkeypatch, capsys
):
    entry = a_book(connection, limit="8")
    checks(connection, entry, [copy("v1|1|0", "10")], [copy("v1|1|0", "7.50")])
    monkeypatch.setenv("BOOK_WATCH_DB_PATH", str(tmp_path / "book-watch.db"))

    assert price_moves.main([]) == 0

    printed = capsys.readouterr().out
    assert "Down 1: 0 under $0.50, 0 $0.50 to $2, 1 over $2" in printed
    assert "Went under the limit: 1." in printed
    for private in ("Stoner", "v1|1|0", "7.50", "$8"):
        assert private not in printed
    assert price_moves.main(["x"]) == 2

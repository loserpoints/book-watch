"""Which copies are new since I last looked (S39, #142)."""

from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from book_watch import db, wantlist
from book_watch.copies import Copy, is_new
from book_watch.ebay.search import Money

LOOKED = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)


def a_copy(first_seen, listed):
    return Copy(
        item_id="v1|1|0",
        title="Crash",
        url="https://www.ebay.com/itm/1",
        price=Money(Decimal("9.99"), "USD"),
        shipping=None,
        tier="certain",
        first_seen=first_seen,
        listed=listed,
    )


def test_a_copy_listed_and_found_since_i_looked_is_new():
    later = LOOKED + timedelta(hours=5)
    assert is_new(a_copy(later, later), LOOKED)


def test_a_copy_i_had_already_seen_is_not_new():
    earlier = LOOKED - timedelta(hours=5)
    assert not is_new(a_copy(earlier, earlier), LOOKED)


def test_a_relisted_copy_is_not_new():
    """A new item id, so first seen after I looked, but eBay keeps the
    original listing date."""
    relisted = a_copy(LOOKED + timedelta(hours=5), LOOKED - timedelta(days=40))
    assert not is_new(relisted, LOOKED)


def test_a_copy_eBay_was_slow_to_show_is_still_new():
    """Listed just before I looked, and in the search only after."""
    lagged = a_copy(LOOKED + timedelta(hours=1), LOOKED - timedelta(hours=2))
    assert is_new(lagged, LOOKED)


def test_the_margin_is_a_day():
    found = LOOKED + timedelta(hours=1)
    assert is_new(a_copy(found, LOOKED - timedelta(hours=23)), LOOKED)
    assert not is_new(a_copy(found, LOOKED - timedelta(hours=25)), LOOKED)


def test_a_copy_with_no_listing_date_falls_back_to_when_it_was_found():
    assert is_new(a_copy(LOOKED + timedelta(hours=1), None), LOOKED)
    assert not is_new(a_copy(LOOKED - timedelta(hours=1), None), LOOKED)


def test_nothing_is_new_on_a_book_never_opened():
    later = LOOKED + timedelta(hours=5)
    assert not is_new(a_copy(later, later), None)


# --- visits -----------------------------------------------------------------


@pytest.fixture
def connection(tmp_path):
    with closing(db.connect(tmp_path / "book-watch.db")) as connection:
        db.migrate(connection)
        wantlist.add(connection, "9780099448396", "Crash")
        connection.commit()
        yield connection


def visit(connection, when):
    wantlist.look(connection, 1, when)
    book = wantlist.get(connection, 1)
    return book.last_looked, book.looked_before_this


def test_the_first_visit_has_nothing_before_it(connection):
    assert visit(connection, LOOKED) == (LOOKED, None)


def test_reopening_within_half_an_hour_is_the_same_visit(connection):
    visit(connection, LOOKED)
    assert visit(connection, LOOKED + timedelta(minutes=20)) == (LOOKED, None)


def test_a_later_visit_marks_against_the_one_before(connection):
    visit(connection, LOOKED)
    later = LOOKED + timedelta(days=2)
    assert visit(connection, later) == (later, LOOKED)

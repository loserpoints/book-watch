"""Tests for the copies a book has, and for working out which numbers are it.

The edition set used to be a table a pass wrote conclusions into. It is now
derived on read from things we observed — what sellers declared, what the
catalogue says those numbers are, who sellers say wrote them.

That is the difference between a rule change reaching every book on the list
and reaching only the next one added, so most of this file is about what a
change to the rules would do to books that already exist.
"""

import pytest

from book_watch import copies, db, wantlist

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

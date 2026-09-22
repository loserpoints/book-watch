"""Tests for reading and writing the want-list."""

import pytest

from book_watch import db, wantlist


@pytest.fixture
def connection(tmp_path):
    conn = db.connect(tmp_path / "book-watch.db")
    db.migrate(conn)
    yield conn
    conn.close()


def test_a_book_can_be_added_and_read_back(connection):
    book = wantlist.add(connection, "9780099448396", "Crash")

    assert book.id
    assert book.isbn == "9780099448396"
    assert book.title == "Crash"
    assert book.added_at


def test_a_title_is_optional(connection):
    book = wantlist.add(connection, "9780099448396")

    assert book.title is None


def test_a_blank_title_is_stored_as_no_title(connection):
    """So the list never shows an empty string where a title should be."""
    book = wantlist.add(connection, "9780099448396", "")

    assert book.title is None


def test_the_same_isbn_cannot_be_added_twice(connection):
    wantlist.add(connection, "9780099448396")

    with pytest.raises(wantlist.DuplicateBook):
        wantlist.add(connection, "9780099448396")


def test_the_list_is_newest_first(connection):
    """Checking on something just added is the common case."""
    for isbn, when in (
        ("9780099448396", "2026-09-01 10:00:00"),
        ("9780141439518", "2026-09-03 10:00:00"),
        ("9780307474278", "2026-09-02 10:00:00"),
    ):
        wantlist.add(connection, isbn)
        connection.execute("UPDATE book SET added_at = ? WHERE isbn = ?", (when, isbn))

    assert [book.isbn for book in wantlist.all_books(connection)] == [
        "9780141439518",
        "9780307474278",
        "9780099448396",
    ]


def test_removing_a_book_takes_it_off_the_list(connection):
    book = wantlist.add(connection, "9780099448396")

    assert wantlist.remove(connection, book.id) is True
    assert wantlist.all_books(connection) == []


def test_removing_a_book_that_is_not_there_says_so(connection):
    assert wantlist.remove(connection, 999) is False


def test_an_empty_list_is_empty(connection):
    assert wantlist.all_books(connection) == []


def test_asking_for_a_book_that_does_not_exist_raises(connection):
    with pytest.raises(LookupError):
        wantlist.get(connection, 999)


def test_a_book_without_an_isbn_can_still_be_stored(connection):
    """The override case: text that is not an ISBN at all."""
    book = wantlist.add(connection, "The Riddle of the Sands 1903", "Childers")

    assert book.isbn == "The Riddle of the Sands 1903"

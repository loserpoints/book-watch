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
    assert book.added_by == "9780099448396"
    assert book.title == "Crash"
    assert book.added_at


def test_a_book_added_with_no_title_is_still_searchable(connection):
    """A work has to have something to search for, so the number stands in.

    It reads the same on the page as it did when the title was simply null,
    and enrichment replaces it with the real one.
    """
    book = wantlist.add(connection, "9780099448396")

    assert book.title == "9780099448396"
    assert book.search_query == "9780099448396"


def test_a_blank_title_is_not_stored_as_a_title(connection):
    """So the list never shows an empty string where a title should be."""
    book = wantlist.add(connection, "9780099448396", "")

    assert book.title == "9780099448396"


def test_a_new_entry_is_a_reader_looking_for_any_edition(connection):
    book = wantlist.add(connection, "9780099448396", "Crash")

    assert book.hunt == wantlist.READER


def test_a_new_entry_has_not_been_enriched_yet(connection):
    """Decision 7: the Open Library questions happen afterwards, in the background."""
    book = wantlist.add(connection, "9780099448396", "Crash")

    assert book.being_enriched is True


def test_two_numbers_for_the_same_book_become_one_entry(connection):
    """Once resolution has connected two ISBNs to one work, they are one book.

    This is the gap decision 26 named as its cost: a reader who would take any
    printing had to add each one separately, and saw a fraction of what was
    for sale.
    """
    first = wantlist.add(connection, "9780099448396", "Crash")
    connection.execute(
        "INSERT INTO edition (work_id, isbn) VALUES (?, ?)",
        (first.work_id, "9780374524128"),
    )

    with pytest.raises(wantlist.DuplicateBook):
        wantlist.add(connection, "9780374524128")


def test_a_book_with_several_known_editions_names_none_of_them(connection):
    """Picking one number to display would be picking arbitrarily."""
    book = wantlist.add(connection, "9780099448396", "Crash")
    connection.execute(
        "INSERT INTO edition (work_id, isbn) VALUES (?, ?)",
        (book.work_id, "9780374524128"),
    )

    reread = wantlist.get(connection, book.id)
    assert reread.edition_count == 2
    assert reread.added_by is None
    # So the search falls back to what decision 33 chose anyway.
    assert reread.search_query == "Crash"


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
        entry = wantlist.add(connection, isbn)
        connection.execute(
            "UPDATE entry SET added_at = ? WHERE id = ?", (when, entry.id)
        )

    assert [book.added_by for book in wantlist.all_books(connection)] == [
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


def test_removing_a_book_keeps_what_was_learned_about_it(connection):
    """The work and its editions are knowledge, not something the person put there.

    Re-adding the book then costs no requests at all.
    """
    book = wantlist.add(connection, "9780099448396", "Crash")

    wantlist.remove(connection, book.id)

    editions = connection.execute(
        "SELECT count(*) AS n FROM edition WHERE isbn = '9780099448396'"
    ).fetchone()
    assert editions["n"] == 1
    assert wantlist.add(connection, "9780099448396").work_id == book.work_id


def test_asking_for_a_book_that_does_not_exist_raises(connection):
    with pytest.raises(LookupError):
        wantlist.get(connection, 999)


def test_a_book_without_an_isbn_can_still_be_stored(connection):
    """The override case: text that is not an ISBN at all."""
    book = wantlist.add(connection, "The Riddle of the Sands 1903", "Childers")

    assert book.added_by == "The Riddle of the Sands 1903"
    assert book.title == "Childers"
    # It is not an ISBN, so it does not become an edition pretending to be one.
    assert book.edition_count == 0
    # And it is still searched for exactly as written (decision 29).
    assert book.search_query == "The Riddle of the Sands 1903"


def test_the_added_date_is_just_the_date(connection):
    book = wantlist.add(connection, "9780099448396")
    connection.execute("UPDATE entry SET added_at = '2026-09-22 18:01:19'")

    assert str(wantlist.get(connection, book.id).added_on) == "2026-09-22"


def test_an_unreadable_added_at_does_not_break_the_page(connection):
    """A hand-edited row should degrade, not take the want-list down."""
    book = wantlist.add(connection, "9780099448396")
    connection.execute("UPDATE entry SET added_at = 'sometime last spring'")

    assert wantlist.get(connection, book.id).added_on is None

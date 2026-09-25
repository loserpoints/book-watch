"""Which cover a book shows, and learning it once for a book that has none yet."""

import pytest

from book_watch import covers, db, wantlist
from book_watch.openlibrary import (
    BudgetExhausted,
    EditionIdentity,
    OpenLibraryUnavailable,
)

# --- whose cover --------------------------------------------------------------


def test_a_reader_is_shown_the_works_cover():
    assert covers.chosen("reader", work_cover=1, edition_cover=2) == 1


def test_a_reader_falls_back_to_an_editions_cover():
    assert covers.chosen("reader", work_cover=None, edition_cover=2) == 2


def test_a_collector_is_shown_the_editions_cover():
    """The printing is the thing being hunted, so its cover is the one to show."""
    assert covers.chosen("collector", work_cover=1, edition_cover=2) == 2


def test_a_collector_falls_back_to_the_works_cover():
    assert covers.chosen("collector", work_cover=1, edition_cover=None) == 1


def test_with_neither_there_is_no_cover():
    assert covers.chosen("reader", work_cover=None, edition_cover=None) is None


def test_a_missing_image_is_a_404_rather_than_a_blank_one():
    """Open Library's blank default would look like a cover that failed to load."""
    assert covers.url(6980524) == (
        "https://covers.openlibrary.org/b/id/6980524-M.jpg?default=false"
    )


# --- learning it later ------------------------------------------------------


class Catalogue:
    def __init__(self, answer, editions=None):
        self.answer = answer
        self.editions = editions or {}
        self.asked = []

    def identify_isbn(self, isbn):
        self.asked.append(isbn)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.editions.get(isbn)

    def work_cover(self, work_id):
        self.asked.append(work_id)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture
def connection(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


def unasked(connection, openlibrary_work_id="OL3511459W"):
    """A book as every book on the list was before covers existed."""
    cursor = connection.execute(
        "INSERT INTO work (title, openlibrary_work_id) VALUES ('Stoner', ?)",
        (openlibrary_work_id,),
    )
    work_id = cursor.lastrowid
    connection.execute(
        "INSERT INTO entry (work_id, hunt) VALUES (?, 'reader')", (work_id,)
    )
    return work_id


def entry_for(connection, work_id):
    [book] = [b for b in wantlist.all_books(connection) if b.work_id == work_id]
    return book


def test_a_book_nobody_has_asked_about_is_not_claimed_to_have_no_cover(connection):
    book = entry_for(connection, unasked(connection))

    assert book.cover is None
    assert not book.has_no_cover


def test_a_cover_is_learned_and_kept(connection):
    work_id = unasked(connection)

    covers.look_up(connection, Catalogue(6980524), work_id)

    assert entry_for(connection, work_id).cover == 6980524


def test_a_cover_is_asked_about_once(connection):
    work_id = unasked(connection)
    catalogue = Catalogue(6980524)

    covers.look_up(connection, catalogue, work_id)
    covers.look_up(connection, catalogue, work_id)

    assert catalogue.asked == ["OL3511459W"]


def test_no_cover_is_an_answer_and_is_not_asked_again(connection):
    work_id = unasked(connection)
    catalogue = Catalogue(None)

    covers.look_up(connection, catalogue, work_id)
    covers.look_up(connection, catalogue, work_id)

    assert entry_for(connection, work_id).has_no_cover
    assert catalogue.asked == ["OL3511459W"]


@pytest.mark.parametrize(
    "failure",
    [OpenLibraryUnavailable("down"), BudgetExhausted("ceiling")],
    ids=["unreachable", "over budget"],
)
def test_failing_to_ask_is_not_written_down_as_no_cover(connection, failure):
    work_id = unasked(connection)

    covers.look_up(connection, Catalogue(failure), work_id)

    book = entry_for(connection, work_id)
    assert book.cover is None
    assert not book.has_no_cover


def test_a_book_with_no_open_library_work_is_not_asked_about(connection):
    """Added by text alone, so there is nothing to ask and no answer to wait for."""
    work_id = unasked(connection, openlibrary_work_id=None)
    catalogue = Catalogue(6980524)

    covers.look_up(connection, catalogue, work_id)

    assert catalogue.asked == []
    assert entry_for(connection, work_id).has_no_cover


def test_a_collector_entry_shows_its_editions_cover(connection):
    """Nothing writes collector entries yet; this is the seam M7 builds on."""
    work_id = unasked(connection)
    connection.execute(
        "UPDATE work SET cover_id = 1, cover_from = 'work' WHERE id = ?", (work_id,)
    )
    edition = connection.execute(
        "INSERT INTO edition (work_id, isbn, cover_id) VALUES (?, '9781590171998', 2)",
        (work_id,),
    ).lastrowid
    connection.execute(
        "INSERT INTO entry (work_id, hunt, edition_id) VALUES (?, 'collector', ?)",
        (work_id, edition),
    )

    hunts = {b.hunt: b.cover for b in wantlist.all_books(connection)}

    assert hunts == {"reader": 1, "collector": 2}


# --- books added by number before there were work ids -------------------------
#
# Migration 003 carried M1's books across with their ISBN and no work id.
# *State of Grace* is one, and S25 first shipped recording it as coverless
# without asking, while Open Library holds two covers for it.

STATE_OF_GRACE = "9780679723004"


def edition(cover_id=None, work_id="OL1998538W"):
    return EditionIdentity(
        isbn=STATE_OF_GRACE,
        title="State of Grace",
        work_id=work_id,
        publisher=None,
        published=None,
        physical_format=None,
        cover_id=cover_id,
    )


def added_by_number(connection, typed=STATE_OF_GRACE):
    """A book as migration 003 left it: a number, and no work to ask about."""
    work_id = connection.execute(
        "INSERT INTO work (title) VALUES ('State of Grace')"
    ).lastrowid
    connection.execute(
        "INSERT INTO entry (work_id, hunt, typed) VALUES (?, 'reader', ?)",
        (work_id, typed),
    )
    return work_id


def test_a_book_with_no_work_is_asked_about_by_its_isbn(connection):
    work_id = added_by_number(connection)
    catalogue = Catalogue(None, {STATE_OF_GRACE: edition(cover_id=419932)})

    covers.look_up(connection, catalogue, work_id)

    assert entry_for(connection, work_id).cover == 419932
    assert catalogue.asked == [STATE_OF_GRACE]


def test_an_edition_with_no_cover_asks_the_work_it_names(connection):
    work_id = added_by_number(connection)
    catalogue = Catalogue(6928523, {STATE_OF_GRACE: edition(cover_id=None)})

    covers.look_up(connection, catalogue, work_id)

    assert entry_for(connection, work_id).cover == 6928523
    assert catalogue.asked == [STATE_OF_GRACE, "OL1998538W"]


def test_a_number_open_library_does_not_hold_has_no_cover(connection):
    work_id = added_by_number(connection)
    catalogue = Catalogue(None, {})

    covers.look_up(connection, catalogue, work_id)

    assert entry_for(connection, work_id).has_no_cover
    assert catalogue.asked == [STATE_OF_GRACE]


def test_text_typed_for_a_book_with_no_isbn_is_not_asked_about(connection):
    """Decision 29's override. It is not a number, so there is no question."""
    work_id = added_by_number(connection, typed="Stoner, 1965 Viking first")
    catalogue = Catalogue(6928523)

    covers.look_up(connection, catalogue, work_id)

    assert catalogue.asked == []
    assert entry_for(connection, work_id).has_no_cover


def test_migration_019_asks_again_only_where_018_never_asked(connection):
    by_number = added_by_number(connection)
    by_text = added_by_number(connection, typed="Stoner, 1965 Viking first")
    by_work = unasked(connection)
    connection.execute("UPDATE work SET cover_asked_at = datetime('now')")
    # Run 019 again over the state 018's first lookup left behind.
    connection.execute("DELETE FROM schema_migration WHERE name LIKE '019_%'")
    db.migrate(connection)

    asked = {
        w: entry_for(connection, w).cover_asked_at is not None
        for w in (by_number, by_text, by_work)
    }

    assert asked == {by_number: False, by_text: True, by_work: True}

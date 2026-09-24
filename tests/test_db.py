"""Tests for the migration runner.

Every test gets its own database in a temporary directory, so none of them
can see another's schema.
"""

import sqlite3

import pytest

from book_watch import db
from book_watch.config import MissingCredentialError, load_database_path


@pytest.fixture
def database(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    yield connection
    connection.close()


def table_names(connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row["name"] for row in rows}


def test_migrating_a_fresh_database_creates_the_schema(database):
    applied = db.migrate(database)

    # Every migration on disk, in filename order. Asserting the exact list
    # rather than a prefix means adding one to the package without adding it
    # here is a failing test rather than a silent gap.
    assert applied == [f.name for f in sorted(db.MIGRATIONS_DIR.glob("*.sql"))]
    assert {"work", "edition", "entry"} <= table_names(database)
    # 003 replaced it. A leftover would be a second place to add a book to.
    assert "book" not in table_names(database)


def test_running_twice_changes_nothing(database):
    first = db.migrate(database)
    second = db.migrate(database)

    assert first
    assert second == []
    recorded = database.execute("SELECT count(*) AS n FROM schema_migration").fetchone()
    assert recorded["n"] == len(first)


def test_a_migration_already_recorded_is_not_run_again(database, monkeypatch, tmp_path):
    """The half-migrated case: some applied, some not.

    Against a throwaway pair rather than the real migrations, which depend on
    each other — 003 reads the table 001 creates, so skipping 001 for real
    would be testing an impossible database.
    """
    two = tmp_path / "migrations"
    two.mkdir()
    (two / "001_first.sql").write_text("CREATE TABLE first (id INTEGER);")
    (two / "002_second.sql").write_text("CREATE TABLE second (id INTEGER);")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", two)
    db.pending(database)  # creates the ledger
    database.execute("INSERT INTO schema_migration (name) VALUES ('001_first.sql')")

    assert db.migrate(database) == ["002_second.sql"]
    assert "first" not in table_names(database)
    assert "second" in table_names(database)


def test_the_parent_directory_is_created(tmp_path):
    """A Fly volume is mounted empty. A missing directory must not be fatal."""
    connection = db.connect(tmp_path / "data" / "nested" / "book-watch.db")
    db.migrate(connection)

    assert "entry" in table_names(connection)
    connection.close()


def test_a_work_can_have_no_title_yet(database):
    """A book added by number alone is untitled until something learns one.

    Writing the number into the title column would have made every work
    searchable by construction, and put a thirteen-digit heading on the page.
    """
    db.migrate(database)

    database.execute("INSERT INTO work (id) VALUES (1)")

    row = database.execute("SELECT title FROM work WHERE id = 1").fetchone()
    assert row["title"] is None


def test_the_same_isbn_cannot_be_two_editions(database):
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")
    database.execute("INSERT INTO edition (work_id, isbn) VALUES (1, '9780099448396')")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            "INSERT INTO edition (work_id, isbn) VALUES (1, '9780099448396')"
        )


def test_editions_without_an_isbn_do_not_collide(database):
    """A 1965 first edition has no number, and neither does the next one."""
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Stoner')")

    database.execute("INSERT INTO edition (work_id, publisher) VALUES (1, 'Viking')")
    database.execute("INSERT INTO edition (work_id, publisher) VALUES (1, 'Longmans')")

    rows = database.execute("SELECT count(*) AS n FROM edition").fetchone()
    assert rows["n"] == 2


def test_a_book_can_only_be_on_the_list_once_as_a_reader_entry(database):
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")
    database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'reader')")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'reader')")


def test_a_reader_entry_may_not_name_an_edition(database):
    """A reader will take any printing. Naming one would mean the other hunt."""
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")
    database.execute("INSERT INTO edition (id, work_id) VALUES (7, 1)")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            "INSERT INTO entry (work_id, hunt, edition_id) VALUES (1, 'reader', 7)"
        )


def test_a_collector_entry_must_name_an_edition(database):
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'collector')")


def test_both_hunts_can_want_the_same_book(database):
    """A reading copy and a particular printing are not a duplicate."""
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Stoner')")
    database.execute("INSERT INTO edition (id, work_id) VALUES (7, 1)")

    database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'reader')")
    database.execute(
        "INSERT INTO entry (work_id, hunt, edition_id) VALUES (1, 'collector', 7)"
    )

    rows = database.execute("SELECT count(*) AS n FROM entry").fetchone()
    assert rows["n"] == 2


def test_an_entry_records_when_it_was_added_without_being_told(database):
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")
    database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'reader')")

    row = database.execute("SELECT added_at FROM entry").fetchone()
    assert row["added_at"]


def test_a_hunt_has_to_be_one_of_the_two(database):
    db.migrate(database)
    database.execute("INSERT INTO work (id, title) VALUES (1, 'Crash')")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO entry (work_id, hunt) VALUES (1, 'browsing')")


def test_a_failing_migration_leaves_no_trace(database, monkeypatch, tmp_path):
    """All-or-nothing, which works because SQLite's DDL is transactional.

    Without this the runner could half-apply a migration, record nothing, and
    then fail forever on the next run against a schema it did not expect.
    """
    broken = tmp_path / "migrations"
    broken.mkdir()
    (broken / "001_initial.sql").write_text(
        "CREATE TABLE good (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE bad (id INTEGER PRIMARY KEY;\n"  # deliberate syntax error
    )
    monkeypatch.setattr(db, "MIGRATIONS_DIR", broken)

    with pytest.raises(db.MigrationError, match="001_initial.sql failed"):
        db.migrate(database)

    assert "good" not in table_names(database)
    assert "bad" not in table_names(database)
    recorded = database.execute("SELECT count(*) AS n FROM schema_migration").fetchone()
    assert recorded["n"] == 0


def test_migrations_run_in_filename_order(database, monkeypatch, tmp_path):
    ordered = tmp_path / "migrations"
    ordered.mkdir()
    (ordered / "002_second.sql").write_text("CREATE TABLE second (id INTEGER);")
    (ordered / "001_first.sql").write_text("CREATE TABLE first (id INTEGER);")
    (ordered / "010_tenth.sql").write_text("CREATE TABLE tenth (id INTEGER);")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", ordered)

    assert db.migrate(database) == [
        "001_first.sql",
        "002_second.sql",
        "010_tenth.sql",
    ]


def test_foreign_keys_are_enforced_on_the_connection(database):
    row = database.execute("PRAGMA foreign_keys").fetchone()

    assert row[0] == 1


def test_the_database_path_must_be_configured(monkeypatch):
    monkeypatch.delenv("BOOK_WATCH_DB_PATH", raising=False)

    with pytest.raises(MissingCredentialError, match="BOOK_WATCH_DB_PATH"):
        load_database_path(use_dotenv=False)


def test_the_database_path_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("BOOK_WATCH_DB_PATH", "/data/book-watch.db")

    assert str(load_database_path(use_dotenv=False)) == "/data/book-watch.db"


# --- 003 over a database that already has books in it -----------------------
#
# The case that matters. There are real rows on the mounted volume, and this
# is the first migration in this project that could destroy any of them.


def at_the_shape_before_003(connection) -> None:
    """Bring a fresh database up to where it stood before 003, and no further."""
    db.pending(connection)  # creates the ledger
    for migration in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
        if migration.name.startswith("003"):
            break
        connection.executescript(migration.read_text())
        connection.execute(
            "INSERT INTO schema_migration (name) VALUES (?)", (migration.name,)
        )


@pytest.fixture
def old_shape_with_rows(database):
    at_the_shape_before_003(database)
    database.executescript(
        """
        INSERT INTO book (id, isbn, title, added_at)
        VALUES (1, '9780099448396', 'Crash', '2026-09-01 10:00:00');

        -- No title: it was going to be filled in by resolution.
        INSERT INTO book (id, isbn, title, added_at)
        VALUES (2, '9781590171998', NULL, '2026-09-02 10:00:00');

        -- An override under decision 29: a book that never had an ISBN.
        INSERT INTO book (id, isbn, title, added_at)
        VALUES (3, 'The Riddle of the Sands 1903', 'Childers',
                '2026-09-03 10:00:00');
        """
    )
    return database


def test_every_existing_book_survives_003(old_shape_with_rows):
    db.migrate(old_shape_with_rows)

    rows = old_shape_with_rows.execute(
        "SELECT id, hunt, added_at FROM entry ORDER BY id"
    ).fetchall()
    assert [row["id"] for row in rows] == [1, 2, 3]
    assert {row["hunt"] for row in rows} == {"reader"}
    # Not re-stamped with today. When it went on the list is the fact.
    assert rows[0]["added_at"] == "2026-09-01 10:00:00"


def test_ids_are_preserved_so_bookmarks_still_work(old_shape_with_rows):
    """The want-list links to /book/{id}. Renumbering breaks every one."""
    db.migrate(old_shape_with_rows)

    row = old_shape_with_rows.execute(
        "SELECT work.title FROM entry JOIN work ON work.id = entry.work_id "
        "WHERE entry.id = 1"
    ).fetchone()
    assert row["title"] == "Crash"


def test_a_book_with_no_title_does_not_acquire_a_fake_one(old_shape_with_rows):
    """It had no title before 003 and it has none after. Its ISBN is elsewhere."""
    db.migrate(old_shape_with_rows)

    row = old_shape_with_rows.execute("SELECT title FROM work WHERE id = 2").fetchone()
    assert row["title"] is None

    typed = old_shape_with_rows.execute(
        "SELECT typed FROM entry WHERE work_id = 2"
    ).fetchone()
    assert typed["typed"] == "9781590171998"


def test_a_real_isbn_becomes_what_the_entry_was_typed_with(old_shape_with_rows):
    """Not an edition. Editions are conclusions; this is what somebody typed."""
    db.migrate(old_shape_with_rows)

    rows = old_shape_with_rows.execute(
        "SELECT id, typed FROM entry ORDER BY id"
    ).fetchall()
    assert [(row["id"], row["typed"]) for row in rows] == [
        (1, "9780099448396"),
        (2, "9781590171998"),
        (3, "The Riddle of the Sands 1903"),
    ]
    # And nothing is left in `edition`, which now holds conclusions only.
    assert (
        old_shape_with_rows.execute("SELECT count(*) AS n FROM edition").fetchone()["n"]
        == 0
    )


def test_an_override_survives_as_text_rather_than_a_fake_edition(old_shape_with_rows):
    """Decision 29's escape hatch. It is not an ISBN, so it does not become one.

    It lives in the same column as a typed ISBN, because it is the same kind
    of thing: what somebody put in the form. Whether it parses as a number is
    a question to ask it, not a reason to store it twice.
    """
    db.migrate(old_shape_with_rows)

    entry = old_shape_with_rows.execute(
        "SELECT typed FROM entry WHERE id = 3"
    ).fetchone()
    assert entry["typed"] == "The Riddle of the Sands 1903"

    editions = old_shape_with_rows.execute(
        "SELECT count(*) AS n FROM edition WHERE work_id = 3"
    ).fetchone()
    assert editions["n"] == 0


def test_a_migrated_book_has_not_been_enriched_yet(old_shape_with_rows):
    """True, and the want-list says so. Nothing has asked Open Library about these."""
    db.migrate(old_shape_with_rows)

    rows = old_shape_with_rows.execute(
        "SELECT count(*) AS n FROM work WHERE enriched_at IS NULL"
    ).fetchone()
    assert rows["n"] == 3


def test_the_notebook_is_left_alone_by_003(old_shape_with_rows):
    """What we already learned from Open Library is not schema churn to redo."""
    old_shape_with_rows.execute(
        "INSERT INTO openlibrary_edition (isbn, found, title) "
        "VALUES ('9781590171998', 1, 'Stoner')"
    )

    db.migrate(old_shape_with_rows)

    row = old_shape_with_rows.execute(
        "SELECT title FROM openlibrary_edition WHERE isbn = '9781590171998'"
    ).fetchone()
    assert row["title"] == "Stoner"


# --- 010 over a database holding both kinds of edition row ------------------
#
# The case this migration exists for. `edition` has been holding an ISBN
# somebody typed and an ISBN a rule concluded, with nothing to tell them
# apart, and that ambiguity is why the wrong book could not be unmatched.


def at_the_shape_before_010(connection) -> None:
    db.pending(connection)
    for migration in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
        if migration.name.startswith("010"):
            break
        connection.executescript(migration.read_text())
        connection.execute(
            "INSERT INTO schema_migration (name) VALUES (?)", (migration.name,)
        )


@pytest.fixture
def both_kinds_of_row(database):
    at_the_shape_before_010(database)
    database.executescript(
        """
        INSERT INTO work (id, title, author) VALUES
            (1, 'Breaking and Entering', 'Joy Williams'),
            (2, 'Crash', 'J. G. Ballard'),
            (3, 'The Riddle of the Sands', NULL);

        -- Added by title: every edition here was concluded by a pass.
        INSERT INTO entry (id, work_id, hunt) VALUES (1, 1, 'reader');
        INSERT INTO edition (work_id, isbn, publisher) VALUES
            (1, '9780394757735', 'Vintage Books'),
            (1, '9781771965231', 'Biblioasis');      -- the wrong book

        -- Added by number: one bare row, which is what `add()` wrote.
        INSERT INTO entry (id, work_id, hunt) VALUES (2, 2, 'reader');
        INSERT INTO edition (work_id, isbn) VALUES (2, '9780099448396');

        -- Added through decision 29's override.
        INSERT INTO entry (id, work_id, hunt, search_text)
        VALUES (3, 3, 'reader', 'The Riddle of the Sands 1903');
        """
    )
    return database


def test_a_typed_number_moves_to_the_entry(both_kinds_of_row):
    db.migrate(both_kinds_of_row)

    row = both_kinds_of_row.execute("SELECT typed FROM entry WHERE id = 2").fetchone()
    assert row["typed"] == "9780099448396"
    # And is no longer duplicated among the conclusions.
    left = both_kinds_of_row.execute(
        "SELECT count(*) AS n FROM edition WHERE work_id = 2"
    ).fetchone()
    assert left["n"] == 0


def test_an_override_moves_to_the_same_column(both_kinds_of_row):
    """It is the same kind of thing: what somebody put in the form."""
    db.migrate(both_kinds_of_row)

    row = both_kinds_of_row.execute("SELECT typed FROM entry WHERE id = 3").fetchone()
    assert row["typed"] == "The Riddle of the Sands 1903"


def test_concluded_editions_stay_put_for_the_next_slice(both_kinds_of_row):
    """Including the wrong one. Deleting conclusions is S15's job, and it can
    do it safely only because nothing typed is mixed in with them."""
    db.migrate(both_kinds_of_row)

    rows = both_kinds_of_row.execute(
        "SELECT isbn FROM edition WHERE work_id = 1 ORDER BY isbn"
    ).fetchall()
    assert [row["isbn"] for row in rows] == ["9780394757735", "9781771965231"]


def test_a_book_added_by_title_was_typed_nothing(both_kinds_of_row):
    db.migrate(both_kinds_of_row)

    row = both_kinds_of_row.execute("SELECT typed FROM entry WHERE id = 1").fetchone()
    assert row["typed"] is None


def test_search_text_is_gone_rather_than_left_meaning_half_of_something(
    both_kinds_of_row,
):
    db.migrate(both_kinds_of_row)

    columns = {row[1] for row in both_kinds_of_row.execute("PRAGMA table_info(entry)")}
    assert "typed" in columns
    assert "search_text" not in columns

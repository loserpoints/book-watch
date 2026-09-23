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
    assert "book" in table_names(database)


def test_running_twice_changes_nothing(database):
    first = db.migrate(database)
    second = db.migrate(database)

    assert first
    assert second == []
    recorded = database.execute("SELECT count(*) AS n FROM schema_migration").fetchone()
    assert recorded["n"] == len(first)


def test_a_migration_already_recorded_is_not_run_again(database, tmp_path):
    """The half-migrated case: some applied, some not."""
    db.pending(database)  # creates the ledger
    database.execute("INSERT INTO schema_migration (name) VALUES ('001_initial.sql')")

    applied = db.migrate(database)

    assert "001_initial.sql" not in applied
    # It did not run, so the table it would have created is absent — while
    # the ones after it ran normally.
    assert "book" not in table_names(database)


def test_the_parent_directory_is_created(tmp_path):
    """A Fly volume is mounted empty. A missing directory must not be fatal."""
    connection = db.connect(tmp_path / "data" / "nested" / "book-watch.db")
    db.migrate(connection)

    assert "book" in table_names(connection)
    connection.close()


def test_a_book_needs_an_isbn(database):
    db.migrate(database)

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO book (title) VALUES ('no isbn')")


def test_the_same_isbn_cannot_be_added_twice(database):
    db.migrate(database)
    database.execute("INSERT INTO book (isbn) VALUES ('9780099448396')")

    with pytest.raises(sqlite3.IntegrityError):
        database.execute("INSERT INTO book (isbn) VALUES ('9780099448396')")


def test_a_book_records_when_it_was_added_without_being_told(database):
    db.migrate(database)
    database.execute("INSERT INTO book (isbn) VALUES ('9780099448396')")

    row = database.execute("SELECT added_at, title FROM book").fetchone()
    assert row["added_at"]
    # Title is optional: resolution fills it in later.
    assert row["title"] is None


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

"""Trying migrations on a copy of the database: the copy, and what it reports."""

import sqlite3
import sys
from pathlib import Path

from book_watch import backup, db

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import try_migrations  # noqa: E402


def test_the_copy_holds_what_the_live_database_holds(tmp_path):
    live = tmp_path / "live.db"
    with sqlite3.connect(live) as connection:
        connection.execute("CREATE TABLE book (title TEXT)")
        connection.execute("INSERT INTO book VALUES ('Geronimo Rex')")

    backup.copy_to(live, tmp_path / "copy.db")

    with sqlite3.connect(tmp_path / "copy.db") as copy:
        assert copy.execute("SELECT title FROM book").fetchall() == [("Geronimo Rex",)]


def test_a_database_already_current_applies_nothing_and_passes(tmp_path, capsys):
    connection = db.connect(tmp_path / "copy.db")
    db.migrate(connection)
    connection.close()

    assert try_migrations.main([str(tmp_path / "copy.db")]) == 0
    assert "applied    nothing" in capsys.readouterr().out


def test_a_table_that_loses_rows_fails(tmp_path, monkeypatch, capsys):
    connection = db.connect(tmp_path / "copy.db")
    db.migrate(connection)
    connection.execute("INSERT INTO work (title) VALUES ('Geronimo Rex')")
    connection.close()
    losing = tmp_path / "migrations"
    losing.mkdir()
    (losing / "999_lose.sql").write_text("DELETE FROM work;")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", losing)

    assert try_migrations.main([str(tmp_path / "copy.db")]) == 1
    assert "Rows lost in: work" in capsys.readouterr().out

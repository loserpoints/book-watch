"""Reading and writing the want-list.

Plain SQL against a connection the caller owns. There is no session, no unit
of work and no repository interface to implement — one user, one writer, and
four queries (decisions.md entry 3).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


class DuplicateBook(Exception):
    """This ISBN is already on the list."""


@dataclass(frozen=True, slots=True)
class Book:
    """One entry on the want-list.

    `isbn` is a validated ISBN-13 for almost every row. It can also hold text
    that is not an ISBN at all, for the books that have none — see
    decisions.md entry 29. Nothing downstream may assume it parses.
    """

    id: int
    isbn: str
    title: str | None
    added_at: str


def add(connection: sqlite3.Connection, isbn: str, title: str | None = None) -> Book:
    """Put a book on the list. Raises `DuplicateBook` if it is already there."""
    try:
        cursor = connection.execute(
            "INSERT INTO book (isbn, title) VALUES (?, ?)",
            (isbn, title or None),
        )
    except sqlite3.IntegrityError as exc:
        # The UNIQUE constraint is the only one this insert can break.
        raise DuplicateBook(isbn) from exc
    return get(connection, int(cursor.lastrowid))


def get(connection: sqlite3.Connection, book_id: int) -> Book:
    row = connection.execute(
        "SELECT id, isbn, title, added_at FROM book WHERE id = ?", (book_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"No book with id {book_id}")
    return _to_book(row)


def all_books(connection: sqlite3.Connection) -> list[Book]:
    """Every book, most recently added first.

    Newest first because the list is read to check on something just added far
    more often than to browse the whole thing.
    """
    rows = connection.execute(
        "SELECT id, isbn, title, added_at FROM book ORDER BY added_at DESC, id DESC"
    )
    return [_to_book(row) for row in rows]


def remove(connection: sqlite3.Connection, book_id: int) -> bool:
    """Delete a book. Returns whether there was one to delete.

    A hard delete, by decisions.md entry 27.
    """
    cursor = connection.execute("DELETE FROM book WHERE id = ?", (book_id,))
    return cursor.rowcount > 0


def _to_book(row: sqlite3.Row) -> Book:
    return Book(
        id=row["id"],
        isbn=row["isbn"],
        title=row["title"],
        added_at=row["added_at"],
    )

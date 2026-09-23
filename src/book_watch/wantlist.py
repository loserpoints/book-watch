"""Reading and writing the want-list.

Plain SQL against a connection the caller owns. There is no session, no unit
of work and no repository interface to implement — one user, one writer, and a
handful of queries (decisions.md entry 3).

Three tables sit behind one `Entry`. A **work** is the book in the abstract, an
**edition** is one printing of it, and an **entry** is a row on the list
pointing at one or the other depending on which hunt it is on. The want-list
screens only ever want the flattened view, so that is what this module hands
back.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

#: The only hunt written today. See migration 003.
READER = "reader"

#: Storable, and nothing reads it yet. Decision 33: the collector surface waits
#: on its own labelling exercise.
COLLECTOR = "collector"


class DuplicateBook(Exception):
    """This book is already on the list."""


@dataclass(frozen=True, slots=True)
class Entry:
    """One row on the want-list, with the work it names.

    `added_by` is what the entry was added with — a number, or the text typed
    for a book that never had one. It is the ISBN only while the work has
    exactly one known edition; once listings have taught us about others,
    naming one of them would be picking arbitrarily.
    """

    id: int
    work_id: int
    hunt: str
    title: str
    author: str | None
    added_at: str
    search_text: str | None
    edition_count: int
    enriched_at: str | None
    _single_isbn: str | None

    @property
    def added_by(self) -> str | None:
        if self.search_text is not None:
            return self.search_text
        return self._single_isbn if self.edition_count == 1 else None

    @property
    def search_query(self) -> str:
        """What to search a marketplace for.

        Today that is the number or text the entry was added with, which is
        what M1 searched and what decision 21 chose. Once a work has several
        known editions there is no single number to use, and decision 33's
        answer — one search on title and author — takes over. S10 makes that
        the only path; this keeps both true in the meantime.
        """
        return self.added_by or " ".join(
            part for part in (self.title, self.author) if part
        )

    @property
    def being_enriched(self) -> bool:
        """Whether Open Library still has questions to answer about this book.

        Decision 7 as amended: a new book costs 10-15 requests that cannot run
        while someone waits, so it is added and shown before they have been
        made. The want-list says so rather than pretending the list is final.
        """
        return self.enriched_at is None

    @property
    def added_on(self) -> date | None:
        """The day this was added, or `None` if the stored value is unreadable.

        SQLite writes `datetime('now')`, which is UTC. Near midnight the date
        shown can therefore be a day ahead of the local one. Harmless while
        this only ever reads "added 2026-09-22"; it needs deciding before
        anything says "today".
        """
        try:
            return datetime.fromisoformat(self.added_at).date()
        except (TypeError, ValueError):
            # A hand-edited row should not take the page down with it.
            return None


_SELECT = """
SELECT entry.id,
       entry.work_id,
       entry.hunt,
       entry.search_text,
       entry.added_at,
       work.title,
       work.author,
       work.enriched_at,
       count(edition.id) AS edition_count,
       min(edition.isbn) AS single_isbn
  FROM entry
  JOIN work ON work.id = entry.work_id
  LEFT JOIN edition ON edition.work_id = work.id
"""


def add(connection: sqlite3.Connection, isbn: str, title: str | None = None) -> Entry:
    """Put a book on the list as a reader entry, to be found in any edition.

    `isbn` is a normalised ISBN-13 for almost every call. It can also be text
    that is not an ISBN at all, for the books that never had one (decision
    29), in which case it becomes the entry's search text rather than an
    edition.

    Adding a number we already hold an edition for joins that edition's work
    rather than making a second one — so two ISBNs of the same book, added by
    hand, collapse into one entry once resolution has connected them.

    Raises `DuplicateBook` if this book already has a reader entry.
    """
    title = (title or "").strip() or None
    is_isbn = len(isbn) == 13 and isbn.isdigit()

    work_id = _existing_work(connection, isbn) if is_isbn else None
    if work_id is None:
        cursor = connection.execute(
            "INSERT INTO work (title) VALUES (?)", (title or isbn,)
        )
        work_id = int(cursor.lastrowid)
        if is_isbn:
            connection.execute(
                "INSERT INTO edition (work_id, isbn) VALUES (?, ?)", (work_id, isbn)
            )

    try:
        cursor = connection.execute(
            """
            INSERT INTO entry (work_id, hunt, edition_id, search_text)
            VALUES (?, ?, NULL, ?)
            """,
            (work_id, READER, None if is_isbn else isbn),
        )
    except sqlite3.IntegrityError as exc:
        # The partial unique index is the only constraint this insert can
        # break: one reader entry per work.
        raise DuplicateBook(isbn) from exc
    return get(connection, int(cursor.lastrowid))


def get(connection: sqlite3.Connection, entry_id: int) -> Entry:
    row = connection.execute(
        f"{_SELECT} WHERE entry.id = ? GROUP BY entry.id", (entry_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"No entry with id {entry_id}")
    return _to_entry(row)


def all_books(connection: sqlite3.Connection) -> list[Entry]:
    """Every entry, most recently added first.

    Newest first because the list is read to check on something just added far
    more often than to browse the whole thing.
    """
    rows = connection.execute(
        f"{_SELECT} GROUP BY entry.id ORDER BY entry.added_at DESC, entry.id DESC"
    )
    return [_to_entry(row) for row in rows]


def remove(connection: sqlite3.Connection, entry_id: int) -> bool:
    """Delete an entry. Returns whether there was one to delete.

    A hard delete, by decision 27 — of the entry only. The work and its
    editions stay: they are what we learned from Open Library and eBay rather
    than something the person put there, re-adding the book then costs no
    requests at all, and a second entry on the same work may still want them.
    """
    cursor = connection.execute("DELETE FROM entry WHERE id = ?", (entry_id,))
    return cursor.rowcount > 0


def _existing_work(connection: sqlite3.Connection, isbn: str) -> int | None:
    row = connection.execute(
        "SELECT work_id FROM edition WHERE isbn = ?", (isbn,)
    ).fetchone()
    return int(row["work_id"]) if row is not None else None


def _to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        work_id=row["work_id"],
        hunt=row["hunt"],
        title=row["title"],
        author=row["author"],
        added_at=row["added_at"],
        search_text=row["search_text"],
        edition_count=row["edition_count"],
        enriched_at=row["enriched_at"],
        _single_isbn=row["single_isbn"],
    )

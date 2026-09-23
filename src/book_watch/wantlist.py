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
from datetime import UTC, date, datetime
from typing import Literal

#: Which hunt an entry is on. A reader will take any edition of the book; a
#: collector wants one particular printing. Every entry is one or the other,
#: and only "reader" is written today — decision 33 leaves the collector
#: surface waiting on its own labelling exercise.
Hunt = Literal["reader", "collector"]


class DuplicateBook(Exception):
    """This book is already on the list."""


@dataclass(frozen=True, slots=True)
class Entry:
    """One row on the want-list, with the work it names.

    `added_by` is what the entry was added with — a number, or the text typed
    for a book that never had one. It is the ISBN only while the work has
    exactly one known edition; once listings have taught us about others,
    naming one of them would be picking arbitrarily.

    `title` is genuinely absent for a book added by number alone, until
    something learns one. Screens use `name`.
    """

    id: int
    work_id: int
    hunt: Hunt
    title: str | None
    author: str | None
    added_at: str
    search_text: str | None
    edition_count: int
    resolved_at: str | None
    enriched_at: str | None
    copies_fetched_at: str | None
    _single_isbn: str | None

    @property
    def added_by(self) -> str | None:
        if self.search_text is not None:
            return self.search_text
        return self._single_isbn if self.edition_count == 1 else None

    @property
    def name(self) -> str:
        """What to call this on screen.

        A book added by number alone has no title, and the number is not one —
        putting it in a heading would claim less than we know, since the ISBN
        is the part we are sure of and it shows on its own line.

        Which of the two missing-title cases this is matters, because they are
        not the same news. Before anything has looked, we have simply not
        asked — true of the books migration 003 carried across. Once we have
        looked, a title still missing means Open Library had no record of the
        number, which is usually a mistyped digit and is the reader's to act
        on rather than ours.
        """
        if self.title:
            return self.title
        return "Looking this up…" if self.resolved_at is None else "Unrecognized ISBN"

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
        )  # an entry always has one or the other

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
       work.resolved_at,
       work.enriched_at,
       work.copies_fetched_at,
       count(edition.id) AS edition_count,
       min(edition.isbn) AS single_isbn
  FROM entry
  JOIN work ON work.id = entry.work_id
  LEFT JOIN edition ON edition.work_id = work.id
"""


def add_identified(
    connection: sqlite3.Connection,
    *,
    title: str,
    author: str | None = None,
    openlibrary_work_id: str | None = None,
    isbn: str | None = None,
) -> Entry:
    """Put a book on the list that Open Library has already told us about.

    Both resolved paths arrive here: a candidate picked from a title search,
    and an ISBN whose record came back. The work is marked resolved, so a
    missing title afterwards can only mean the lookup found nothing.
    """
    work_id = _existing_work(connection, isbn) if isbn else None
    if work_id is None:
        cursor = connection.execute(
            """
            INSERT INTO work (title, author, openlibrary_work_id, resolved_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (title, author, openlibrary_work_id),
        )
        work_id = int(cursor.lastrowid)
        if isbn:
            connection.execute(
                "INSERT INTO edition (work_id, isbn) VALUES (?, ?)", (work_id, isbn)
            )
    return _add_reader_entry(
        connection, work_id, search_text=None, duplicate=isbn or title
    )


def add(connection: sqlite3.Connection, isbn: str, title: str | None = None) -> Entry:
    """Put a book on the list without anything having recognised it.

    Two callers, both deliberate. A number Open Library has no record of,
    added anyway because the person holding the book says it is real. And
    decision 29's override: text that is not an ISBN at all, for the books
    that never had one, searched exactly as written.

    `resolved_at` is set for the first and left null for the second. Asking
    about something that is not a number would be asking a question with no
    answer, so no claim is made about it either way.
    """
    title = (title or "").strip() or None
    is_isbn = len(isbn) == 13 and isbn.isdigit()

    work_id = _existing_work(connection, isbn) if is_isbn else None
    if work_id is None:
        # No title, no invention. A number that was looked up and not found
        # stays untitled; an override entry takes the text typed, because that
        # text is the only name it has.
        cursor = connection.execute(
            "INSERT INTO work (title, resolved_at) VALUES (?, ?)",
            (
                title if is_isbn else title or isbn,
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S") if is_isbn else None,
            ),
        )
        work_id = int(cursor.lastrowid)
        if is_isbn:
            connection.execute(
                "INSERT INTO edition (work_id, isbn) VALUES (?, ?)", (work_id, isbn)
            )

    return _add_reader_entry(
        connection, work_id, search_text=None if is_isbn else isbn, duplicate=isbn
    )


def _add_reader_entry(
    connection: sqlite3.Connection,
    work_id: int,
    *,
    search_text: str | None,
    duplicate: str,
) -> Entry:
    try:
        cursor = connection.execute(
            """
            INSERT INTO entry (work_id, hunt, edition_id, search_text)
            VALUES (?, 'reader', NULL, ?)
            """,
            (work_id, search_text),
        )
    except sqlite3.IntegrityError as exc:
        # The partial unique index is the only constraint this insert can
        # break: one reader entry per work.
        raise DuplicateBook(duplicate) from exc
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


def _existing_work(connection: sqlite3.Connection, isbn: str | None) -> int | None:
    if isbn is None:
        return None
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
        resolved_at=row["resolved_at"],
        enriched_at=row["enriched_at"],
        copies_fetched_at=row["copies_fetched_at"],
        _single_isbn=row["single_isbn"],
    )

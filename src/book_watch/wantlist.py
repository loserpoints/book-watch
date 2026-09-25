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
from decimal import Decimal, InvalidOperation
from typing import Literal

from book_watch import covers
from book_watch.ebay.search import Money

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

    `typed` is exactly what somebody put in the add form: an ISBN, or the
    text for a book that never had one (decision 29). It is a fact about
    their intent and can never be wrong, which is why it lives here rather
    than among the editions a rule inferred — those are conclusions, and
    conclusions from rules that keep changing have to stay re-derivable.

    `title` is genuinely absent for a book added by number alone, until
    something learns one. Screens use `name`.
    """

    id: int
    work_id: int
    hunt: Hunt
    title: str | None
    author: str | None
    added_at: str
    typed: str | None
    edition_count: int
    resolved_at: str | None
    enriched_at: str | None
    copies_fetched_at: str | None
    #: The most this entry will pay, delivered, or None. Both fields are set
    #: together or neither is: a number with no currency is not a price.
    ceiling: str | None = None
    ceiling_currency: str | None = None
    #: The work's cover id, and when anybody asked. See migration 018 for why
    #: those are three states and not two.
    work_cover: int | None = None
    cover_asked_at: str | None = None
    #: The cover of the printing a collector entry hunts. Always None for a
    #: reader, who hunts no printing in particular.
    edition_cover: int | None = None

    @property
    def cover(self) -> int | None:
        """The cover this entry shows, by the rule in `covers.chosen`."""
        return covers.chosen(self.hunt, self.work_cover, self.edition_cover)

    @property
    def has_no_cover(self) -> bool:
        """Whether Open Library has told us there is no cover to show.

        Distinct from not knowing yet. A book nobody has asked about may well
        have a cover, and drawing the placeholder over it would be claiming
        otherwise.
        """
        return self.cover is None and self.cover_asked_at is not None

    @property
    def will_pay(self) -> Money | None:
        """The ceiling as money, or None when there is not one.

        Parsed here rather than stored as a number, for the reason decision 1
        gives: a price that has been through a float is a different price.
        """
        if self.ceiling is None or self.ceiling_currency is None:
            return None
        try:
            return Money(Decimal(self.ceiling), self.ceiling_currency)
        except InvalidOperation:
            return None

    @property
    def added_by(self) -> str | None:
        """What this entry was added with, if that was anything in particular.

        A book added by title has none, and naming one of the editions since
        learned would be answering a different question.
        """
        return self.typed

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
        return self.typed or " ".join(
            part for part in (self.title, self.author) if part
        )  # an entry always has one or the other

    @property
    def being_enriched(self) -> bool:
        """Whether there is known work outstanding on this book.

        Copies have been found and not yet examined. A book nobody has opened
        has no copies either, so there is nothing to dig through and the
        want-list says nothing — the app does not advertise work it has not
        started.

        Decision 7 as amended: examining a book costs ten to fifteen Open
        Library requests that cannot run while somebody waits, so it happens
        afterwards and the list says so while it does.
        """
        return self.copies_fetched_at is not None and self.enriched_at is None

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
       entry.typed,
       entry.added_at,
       entry.ceiling,
       entry.ceiling_currency,
       work.title,
       work.author,
       work.resolved_at,
       work.enriched_at,
       work.copies_fetched_at,
       work.cover_id AS work_cover,
       work.cover_asked_at,
       hunted.cover_id AS edition_cover,
       count(edition.id) AS edition_count
  FROM entry
  JOIN work ON work.id = entry.work_id
  LEFT JOIN edition ON edition.work_id = work.id
  LEFT JOIN edition AS hunted ON hunted.id = entry.edition_id
"""


def add_identified(
    connection: sqlite3.Connection,
    *,
    title: str,
    author: str | None = None,
    openlibrary_work_id: str | None = None,
    isbn: str | None = None,
    work_cover: int | None = None,
    edition_cover: int | None = None,
) -> Entry:
    """Put a book on the list that Open Library has already told us about.

    Both resolved paths arrive here: a candidate picked from a title search,
    and an ISBN whose record came back. The work is marked resolved, so a
    missing title afterwards can only mean the lookup found nothing.

    Each path brings the cover it already has, so neither costs a request.
    A title search reports the work's cover, and its absence is an answer:
    Open Library holds none. A number reports only its edition's, which
    stands in for the work's; if it has none, the work's is still unknown,
    and `covers.look_up` asks later rather than while somebody waits.
    """
    if work_cover is not None or isbn is None:
        cover, cover_from, asked = work_cover, "work", True
    else:
        cover, cover_from, asked = edition_cover, "edition", edition_cover is not None
    work_id = _existing_work(connection, isbn) if isbn else None
    if work_id is None:
        cursor = connection.execute(
            """
            INSERT INTO work (
                title, author, openlibrary_work_id, resolved_at,
                cover_id, cover_from, cover_asked_at
            )
            VALUES (
                ?, ?, ?, datetime('now'),
                ?, ?, CASE WHEN ? THEN datetime('now') END
            )
            """,
            (
                title,
                author,
                openlibrary_work_id,
                cover,
                cover_from if cover is not None else None,
                asked,
            ),
        )
        work_id = int(cursor.lastrowid)
    # No edition row. The number goes on the entry, because it is what
    # somebody typed rather than something a rule concluded, and `edition`
    # now holds conclusions only.
    return _add_reader_entry(connection, work_id, typed=isbn, duplicate=isbn or title)


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

    return _add_reader_entry(connection, work_id, typed=isbn, duplicate=isbn)


def _add_reader_entry(
    connection: sqlite3.Connection,
    work_id: int,
    *,
    typed: str | None,
    duplicate: str,
) -> Entry:
    try:
        cursor = connection.execute(
            """
            INSERT INTO entry (work_id, hunt, edition_id, typed)
            VALUES (?, 'reader', NULL, ?)
            """,
            (work_id, typed),
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


def set_ceiling(
    connection: sqlite3.Connection, entry_id: int, amount: str | None, currency: str
) -> Entry:
    """Set or clear what this entry will pay, delivered.

    An empty amount clears it, which has to be possible: a ceiling somebody
    can set and not unset is a trap, and there is no other way to change your
    mind from the page.

    Rejects an amount that is not a price rather than storing it and failing
    to compare later, which would look like "no copy is under" and give no
    clue why.
    """
    cleaned = (amount or "").strip()
    if not cleaned:
        connection.execute(
            "UPDATE entry SET ceiling = NULL, ceiling_currency = NULL WHERE id = ?",
            (entry_id,),
        )
        connection.commit()
        return get(connection, entry_id)

    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"{cleaned!r} is not an amount.") from None
    if parsed <= 0:
        raise ValueError("A ceiling has to be more than nothing.")

    connection.execute(
        "UPDATE entry SET ceiling = ?, ceiling_currency = ? WHERE id = ?",
        (str(parsed), currency.strip().upper(), entry_id),
    )
    connection.commit()
    return get(connection, entry_id)


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
    """Which book, if any, this number already belongs to.

    Both places it can be known from: somebody typed it, or a pass concluded
    it. Either makes adding it again the same book rather than a second one.
    """
    if isbn is None:
        return None
    row = connection.execute(
        """
        SELECT work_id FROM edition WHERE isbn = ?
        UNION
        SELECT work_id FROM entry WHERE typed = ?
        LIMIT 1
        """,
        (isbn, isbn),
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
        typed=row["typed"],
        edition_count=row["edition_count"],
        resolved_at=row["resolved_at"],
        enriched_at=row["enriched_at"],
        copies_fetched_at=row["copies_fetched_at"],
        ceiling=row["ceiling"],
        ceiling_currency=row["ceiling_currency"],
        work_cover=row["work_cover"],
        cover_asked_at=row["cover_asked_at"],
        edition_cover=row["edition_cover"],
    )

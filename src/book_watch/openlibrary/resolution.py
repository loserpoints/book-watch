"""The notebook: ask Open Library once, then never again.

`Resolver` is what the rest of the app talks to. It answers the same question
`OpenLibraryClient.identify_isbn` does, but reads what we already know first,
and writes down whatever it learns.

The three states a number can be in — never asked about, known, or known to be
absent from Open Library — are handled here so callers see only two: an
identity, or `None`. Decision 33 needs that `None` to mean "Open Library does
not hold this", and nothing else, which is why being unable to reach Open
Library raises instead.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from book_watch.isbn import normalise
from book_watch.openlibrary.client import OpenLibraryClient
from book_watch.openlibrary.models import EditionIdentity

#: How long to leave a recorded miss before asking again.
#:
#: What a number *is* cannot change, so a found record never expires. A miss
#: can: Open Library gains records. Slowly, though, and the misses we measured
#: were all non-English editions — the population it is structurally weakest
#: on — so a quarter is four questions a year per unknown number rather than
#: one a day.
MISS_LIFETIME = timedelta(days=90)

_Now = Callable[[], datetime]

_COLUMNS = "isbn, found, title, work_id, publisher, published, physical_format"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Resolver:
    """Answers "what is this number?" from the notebook, asking only when it must."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        client: OpenLibraryClient,
        *,
        now: _Now = _utcnow,
        miss_lifetime: timedelta = MISS_LIFETIME,
    ) -> None:
        self._connection = connection
        self._client = client
        self._now = now
        self._miss_lifetime = miss_lifetime

    def identify(self, isbn: str) -> EditionIdentity | None:
        """What this number is, or `None` if Open Library has no record of it.

        Asks Open Library only when the notebook has nothing usable. Raises
        `OpenLibraryUnavailable` if the question has to be asked and cannot be.
        """
        normalised = normalise(isbn)
        if normalised is None:
            raise ValueError(
                f"{isbn!r} is not a valid ISBN. Normalise before asking, and "
                "skip the ones that come back None rather than asking anyway."
            )

        row = self._connection.execute(
            f"SELECT {_COLUMNS}, asked_at FROM openlibrary_edition WHERE isbn = ?",
            (normalised,),
        ).fetchone()

        if row is not None and not self._stale(row):
            return _row_to_identity(row)

        identity = self._client.identify_isbn(normalised)
        self._remember(normalised, identity)
        return identity

    def known(self, isbn: str) -> bool:
        """Whether the notebook can answer for this number without asking.

        For the enrichment worker, which wants to count what a new book will
        cost before spending it.
        """
        normalised = normalise(isbn)
        if normalised is None:
            return False
        row = self._connection.execute(
            "SELECT found, asked_at FROM openlibrary_edition WHERE isbn = ?",
            (normalised,),
        ).fetchone()
        return row is not None and not self._stale(row)

    def _stale(self, row: sqlite3.Row) -> bool:
        if row["found"]:
            return False
        asked_at = _parse_timestamp(row["asked_at"])
        if asked_at is None:
            return True
        return self._now() - asked_at > self._miss_lifetime

    def _remember(self, isbn: str, identity: EditionIdentity | None) -> None:
        self._connection.execute(
            f"""
            INSERT INTO openlibrary_edition ({_COLUMNS}, asked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (isbn) DO UPDATE SET
                found           = excluded.found,
                title           = excluded.title,
                work_id         = excluded.work_id,
                publisher       = excluded.publisher,
                published       = excluded.published,
                physical_format = excluded.physical_format,
                asked_at        = excluded.asked_at
            """,
            (
                isbn,
                1 if identity is not None else 0,
                identity.title if identity else None,
                identity.work_id if identity else None,
                identity.publisher if identity else None,
                identity.published if identity else None,
                identity.physical_format if identity else None,
            ),
        )


def _row_to_identity(row: sqlite3.Row) -> EditionIdentity | None:
    if not row["found"]:
        return None
    return EditionIdentity(
        isbn=row["isbn"],
        title=row["title"],
        work_id=row["work_id"],
        publisher=row["publisher"],
        published=row["published"],
        physical_format=row["physical_format"],
    )


def _parse_timestamp(raw: object) -> datetime | None:
    """SQLite's `datetime('now')` format, which is UTC without saying so."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    except ValueError:
        return None

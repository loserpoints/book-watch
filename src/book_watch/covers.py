"""Which cover a book shows, and where its image comes from.

Only cover *ids* are ours. The images stay on Open Library's cover server and
the page points at them, because that is what their covers API is for — it is
"intended for displaying covers on public facing websites and not for bulk
download" (decision 56). So nothing here fetches an image, and nothing stores
one.

Whose cover follows the hunt:

    reader     the work's cover — any edition will do, and the work's cover is
               the one somebody recognises
    collector  the edition's cover — that printing is the thing being hunted

Each falls back to the other, because a cover of the right book is better
than a placeholder, and a placeholder is better than a cover of the wrong one.
"""

from __future__ import annotations

import sqlite3
from typing import Literal, Protocol

from book_watch.openlibrary import OpenLibraryError

COVERS_URL = "https://covers.openlibrary.org/b/id"

#: Open Library's three sizes. S is 40-odd pixels wide, which is too small for
#: a list row on a phone screen at twice its density; M is about 180.
Size = Literal["S", "M", "L"]


class WorkCovers(Protocol):
    def work_cover(self, work_id: str) -> int | None: ...


def url(cover_id: int, size: Size = "M") -> str:
    """Where the browser loads a cover from.

    `default=false` makes a missing image a 404 rather than Open Library's
    blank placeholder, so the page can show its own instead of an empty frame
    that looks like a cover failed to arrive.
    """
    return f"{COVERS_URL}/{cover_id}-{size}.jpg?default=false"


def chosen(hunt: str, work_cover: int | None, edition_cover: int | None) -> int | None:
    """The cover this entry shows, by the rule at the top of this module."""
    if hunt == "collector":
        return edition_cover or work_cover
    return work_cover or edition_cover


def look_up(
    connection: sqlite3.Connection, catalogue: WorkCovers, work_id: int
) -> None:
    """Learn a work's cover, once, for a book that arrived without one.

    Runs when the browser asks for the cover, never while the list renders, so
    the list appears at once and a cover arrives after it (decision 41's rule
    for any slow Open Library work).

    Writes nothing when Open Library cannot be asked, so the next view tries
    again. A book with no Open Library work — one added by text alone — cannot
    be asked about at all, and is recorded as having no cover rather than being
    retried on every view for an answer that cannot come.
    """
    row = connection.execute(
        "SELECT openlibrary_work_id, cover_asked_at FROM work WHERE id = ?",
        (work_id,),
    ).fetchone()
    if row is None or row["cover_asked_at"] is not None:
        return

    cover: int | None = None
    if row["openlibrary_work_id"]:
        try:
            cover = catalogue.work_cover(row["openlibrary_work_id"])
        except OpenLibraryError:
            # Unreachable, or our own ceiling reached. Neither is an answer
            # about the cover, so neither may be written down as one.
            return

    connection.execute(
        """
        UPDATE work
           SET cover_id = ?,
               cover_from = CASE WHEN ? IS NULL THEN NULL ELSE 'work' END,
               cover_asked_at = datetime('now')
         WHERE id = ? AND cover_asked_at IS NULL
        """,
        (cover, cover, work_id),
    )
    connection.commit()

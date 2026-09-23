"""A ceiling on how much we ask of Open Library, and a record of what we asked.

Open Library publishes no daily limit — what they enforce is one request per
second per IP, which the client's pacing handles. This is a different thing:
a bound on our own mistakes.

The failure worth defending against is not a person adding books too fast. It
is a loop that should have read the cache and didn't, running unattended. Paced
at a second and a half, that is 2,400 requests a day, every day, from one hobby
user against a non-profit that asks for low volume. The ceiling turns it into a
loud failure after a few hundred.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import timedelta

from book_watch.openlibrary.errors import OpenLibraryError

#: Requests allowed in `WINDOW`.
#:
#: Sized against real use rather than against a published figure, because
#: there is no published figure. Adding a book costs one request; resolving
#: the numbers in one book's listings costs ten to fifteen. A busy, entirely
#: legitimate day — ten books added and enriched — is about 160. This is
#: roughly three times that, and about a fifth of what an unattended loop
#: would manage.
DAILY_CEILING = 500

WINDOW = timedelta(days=1)

ConnectFn = Callable[[], sqlite3.Connection]


class BudgetExhausted(OpenLibraryError):
    """The ceiling has been reached, so the request was not made.

    Deliberately not `OpenLibraryUnavailable`. That means *they* could not
    answer; this means *we* declined to ask. A caller that retried this on a
    timer would be doing exactly the thing the ceiling exists to stop.
    """


class CallBudget:
    """Counts every request to Open Library, and refuses past a ceiling."""

    def __init__(
        self,
        connect: ConnectFn,
        *,
        ceiling: int = DAILY_CEILING,
        window: timedelta = WINDOW,
    ) -> None:
        self._connect = connect
        self._ceiling = ceiling
        self._window = window

    def spend(self, endpoint: str) -> None:
        """Record one request, or refuse to allow it.

        Recorded before the request goes out rather than after it comes back.
        A request that times out still reached them, and a version of this
        that counted only successes would let a loop of failures run for ever.

        Checking and recording are not atomic, so N callers racing could
        between them go N-1 over. There is one caller (decision 8), and a
        ceiling whose job is to catch a runaway does not need to be exact at
        its edge.
        """
        with closing(self._connect()) as connection:
            if self._spent(connection) >= self._ceiling:
                raise BudgetExhausted(
                    f"{self._ceiling} Open Library requests in the last "
                    f"{self._window}, which is far past anything this app does "
                    "in normal use. Something is looping. Nothing has been "
                    "sent."
                )
            connection.execute(
                "INSERT INTO openlibrary_call (endpoint) VALUES (?)", (endpoint,)
            )
            connection.commit()

    def spent(self) -> int:
        """How many requests have been made inside the window."""
        with closing(self._connect()) as connection:
            return self._spent(connection)

    def _spent(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT count(*) AS n FROM openlibrary_call WHERE at > datetime('now', ?)",
            (f"-{int(self._window.total_seconds())} seconds",),
        ).fetchone()
        return int(row["n"])

    def forget_older_than(self, keep: timedelta = timedelta(days=30)) -> int:
        """Drop rows too old to affect any window, and return how many.

        A row a second for ever is not a lot, but it is also not nothing, and
        the volume it sits on is 1 GB.
        """
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM openlibrary_call WHERE at < datetime('now', ?)",
                (f"-{int(keep.total_seconds())} seconds",),
            )
            connection.commit()
            return cursor.rowcount

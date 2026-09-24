"""Find out what a book's copies actually are, without anybody waiting.

Two phases, in order, because the second needs the first:

1. **What did the seller declare?** One eBay call per copy never asked about,
   at about half a second each.
2. **What is that number?** One Open Library call per number never asked
   about, paced at one every 1.5 seconds and counted against a daily ceiling.

Neither can run while somebody waits. Decision 40 measured why: a book with
fifty copies is twenty-five seconds of eBay alone, against a page that should
answer in two. So the page shows what is known, this fills in the rest, and
the copies firm up from *possible* to *certain* as it goes.

**Resumable by construction.** Every answer is written down the moment it
arrives, so a pass that dies halfway — a restart, an outage, a ceiling —
leaves everything it learned and the next pass picks up where it stopped.
Nothing here needs to be transactional because nothing here is a transaction.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass

from book_watch.ebay.declarations import Declarations
from book_watch.ebay.errors import EbayError
from book_watch.isbn import normalise
from book_watch.openlibrary import BudgetExhausted, OpenLibraryUnavailable, Resolver

logger = logging.getLogger(__name__)

ConnectFn = Callable[[], sqlite3.Connection]

#: Books currently being worked on by this process.
#:
#: A page refresh during a pass would otherwise start a second one, and the
#: two would ask the same questions twice. This is not a lock on the data —
#: everything written is idempotent — it is a way of not being rude twice.
_in_progress: set[int] = set()
_guard = threading.Lock()


@dataclass(frozen=True, slots=True)
class Pass:
    """What one pass managed to do."""

    examined: int = 0
    resolved: int = 0
    #: Whether this pass gave the book itself a title it had been missing.
    identified: bool = False
    completed: bool = False
    stopped_because: str | None = None


def enrich(
    connect: ConnectFn,
    work_id: int,
    declarations_for: Callable[[sqlite3.Connection], Declarations],
    resolver_for: Callable[[sqlite3.Connection], Resolver],
) -> Pass:
    """Examine one book's copies, and find out what the numbers on them mean.

    Opens its own connection: this runs on a different thread from the request
    that started it, and SQLite connections belong to the thread that made
    them.
    """
    with _guard:
        if work_id in _in_progress:
            return Pass(stopped_because="already running")
        _in_progress.add(work_id)
    try:
        with connect() as connection:
            return _run(connection, work_id, declarations_for, resolver_for)
    finally:
        with _guard:
            _in_progress.discard(work_id)


def _run(
    connection: sqlite3.Connection,
    work_id: int,
    declarations_for: Callable[[sqlite3.Connection], Declarations],
    resolver_for: Callable[[sqlite3.Connection], Resolver],
) -> Pass:
    title = connection.execute(
        "SELECT title FROM work WHERE id = ?", (work_id,)
    ).fetchone()
    if title is None:
        return Pass(stopped_because="no such book")

    declarations = declarations_for(connection)
    examined = 0
    identified = False
    numbers: set[str] = set()

    item_ids = [
        row["item_id"]
        for row in connection.execute(
            "SELECT item_id FROM copy WHERE work_id = ?", (work_id,)
        )
    ]
    for item_id in item_ids:
        already = declarations.known(item_id)
        try:
            declared = declarations.of(item_id)
        except EbayError as exc:
            # Leave what was learned and stop. The next pass resumes.
            connection.commit()
            logger.warning("Enriching %s stopped: %s", work_id, exc)
            return Pass(examined=examined, stopped_because="ebay unavailable")
        if not already:
            examined += 1
        if declared.isbn:
            numbers.add(declared.isbn)
    connection.commit()

    resolver = resolver_for(connection)
    resolved = 0
    wanted = title["title"]

    # A book added before there was anything to identify it with never got a
    # title, and nothing since would ever give it one: only the add path
    # writes `resolved_at`, and these rows predate it. They sit on the
    # want-list reading "Looking this up…" for ever.
    #
    # Its own number is already in `edition`, so the answer costs one lookup
    # that this pass was going to make anyway. Healing it here rather than in
    # a one-off backfill means the next such gap heals itself too.
    if wanted is None:
        wanted, identified = _identify_the_book(connection, work_id, resolver)
    for isbn in sorted(numbers):
        already = resolver.known(isbn)
        try:
            # The answer is written into the notebook by the resolver; a
            # pass no longer draws any conclusion from it. Which numbers are
            # this book is worked out on read, from what is stored here.
            resolver.identify(isbn)
        except BudgetExhausted as exc:
            connection.commit()
            # Not retried, and not treated as an outage. Decision 39: a caller
            # that retries this on a timer is the exact failure it prevents.
            logger.warning("Enriching %s stopped at the ceiling: %s", work_id, exc)
            return Pass(examined, resolved, stopped_because="over budget")
        except OpenLibraryUnavailable as exc:
            connection.commit()
            logger.warning("Enriching %s stopped: %s", work_id, exc)
            return Pass(examined, resolved, stopped_because="open library")
        if not already:
            resolved += 1
    connection.commit()

    connection.execute(
        "UPDATE work SET enriched_at = datetime('now') WHERE id = ?", (work_id,)
    )
    connection.commit()
    return Pass(examined, resolved, completed=True, identified=identified)


def _identify_the_book(
    connection: sqlite3.Connection, work_id: int, resolver: Resolver
) -> tuple[str | None, bool]:
    """Give an untitled book its title, from the number it was added with.

    The number somebody typed, not one a pass inferred — a book with no title
    has had no pass, so there is nothing inferred to read, and the typed value
    is the only thing that was ever known about it.
    """
    for row in connection.execute(
        "SELECT typed AS isbn FROM entry WHERE work_id = ? AND typed IS NOT NULL "
        "ORDER BY id",
        (work_id,),
    ):
        if normalise(row["isbn"]) is None:
            continue  # an override: text that was never a number to look up
        identity = resolver.identify(row["isbn"])
        if identity is None:
            continue
        connection.execute(
            "UPDATE work SET title = ?, resolved_at = datetime('now') WHERE id = ?",
            (identity.title, work_id),
        )
        return identity.title, True
    # Asked, and the catalogue has nothing. Recording that stops the want-list
    # claiming somebody is still looking, which would no longer be true.
    connection.execute(
        "UPDATE work SET resolved_at = datetime('now') WHERE id = ?", (work_id,)
    )
    return None, True

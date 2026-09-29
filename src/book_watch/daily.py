"""Check every book once a day, whether or not the app is opened (S37, #141).

At 7am New York time every book is searched, one at a time, and any new
copies are examined before the next book starts. A run that a restart
interrupted, or that the app was down for, runs as soon as the app is back:
the rule is "a run has finished since 7am today", not "it is 7am".

Started only by the production entrypoint, never by `create_app`, so tests
and the compliance endpoint never start a thread they did not ask for. The
thread touches the database only when it checks whether a run is due, so a
misconfigured database is logged, loudly and every minute, and breaks
nothing else.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as clock_time
from zoneinfo import ZoneInfo

from book_watch import enrichment, sweeps, wantlist
from book_watch.alerts import AlertError
from book_watch.config import MissingCredentialError
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import DEFAULT_LIMIT

logger = logging.getLogger(__name__)

ConnectFn = Callable[[], sqlite3.Connection]
SearchFn = Callable[..., list]
SpentFn = Callable[[], int]
#: Sends the morning email, returning how many copies it listed (S40).
NotifyFn = Callable[[], int]

#: When the run starts. New York time, so it stays at 7am across daylight
#: saving.
ZONE = ZoneInfo("America/New_York")
RUN_AT = clock_time(7, 0)

#: How long since a run last finished before the want list says one is
#: missing. A day and a bit, so a run that finishes a little later than
#: yesterday's never reads as missed.
OVERDUE = timedelta(hours=26)

#: A run with no finish this long after it started was cut off, by a
#: restart or a crash, rather than still going.
ABANDONED = timedelta(hours=2)

#: How often the thread asks whether a run is due.
POLL_SECONDS = 60

#: SQLite's own `datetime('now')` format, in UTC.
STORED = "%Y-%m-%d %H:%M:%S"


def _stored(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(STORED)


def _read(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.strptime(value, STORED).replace(tzinfo=UTC)


def due(connection: sqlite3.Connection, now: datetime) -> bool:
    """Whether today's run is still owed: it is past 7am in New York, and no
    run has finished since then."""
    local = now.astimezone(ZONE)
    if local.time() < RUN_AT:
        return False
    since = datetime.combine(local.date(), RUN_AT, ZONE)
    row = connection.execute(
        "SELECT 1 FROM daily_run WHERE started_at >= ? AND finished_at IS NOT NULL",
        (_stored(since),),
    ).fetchone()
    return row is None


def run(
    connect: ConnectFn,
    search: SearchFn,
    enrich: enrichment.EnrichFn,
    spent: SpentFn,
    notify: NotifyFn | None = None,
) -> int:
    """Search every book once, examining new copies as it goes, and record
    how it went. Returns the run's id.

    One book at a time, and each book's pass finishes before the next search,
    so the run never has two requests to the same service in flight. A book
    whose search fails is counted and the run carries on: one dead book must
    not cost the other nine their morning.
    """
    with closing(connect()) as connection:
        run_id = connection.execute("INSERT INTO daily_run DEFAULT VALUES").lastrowid
        connection.commit()
        books = [book.id for book in wantlist.all_books(connection)]
    before = spent()
    failed = 0
    throttled = False
    crashed = False
    emailed = 0
    email_failed = False
    try:
        for book_id in books:
            with closing(connect()) as connection:
                try:
                    book = wantlist.get(connection, book_id)
                except LookupError:
                    continue  # Removed since the run started.
                try:
                    sweeps.store(
                        connection,
                        book.work_id,
                        search(book.search_query, DEFAULT_LIMIT, scope="us"),
                        asked_for=DEFAULT_LIMIT,
                        scope="us",
                    )
                    connection.commit()
                except (MissingCredentialError, EbayError) as exc:
                    logger.warning("Daily check could not search %s: %s", book_id, exc)
                    failed += 1
                    continue
                book = wantlist.get(connection, book_id)
            if book.being_enriched and not enrichment.busy(book.work_id):
                result = enrichment.queued(enrich, book.work_id)()
                if getattr(result, "stopped_because", None) == "over budget":
                    throttled = True
        # After every book, so the email covers the whole morning.
        if notify is not None:
            try:
                emailed = notify()
            except AlertError as exc:
                # For the logs, not the app: the check itself went fine, and
                # nothing was recorded as sent, so tomorrow tries again.
                logger.warning("Daily check could not send its email: %s", exc)
                email_failed = True
    except Exception:
        crashed = True
        raise
    finally:
        outcome = "failed" if failed or crashed else "throttled" if throttled else "ok"
        with closing(connect()) as connection:
            connection.execute(
                "UPDATE daily_run SET finished_at = datetime('now'), outcome = ?, "
                "books = ?, failed = ?, openlibrary_spent = ?, emailed = ?, "
                "email_failed = ? WHERE id = ?",
                (
                    outcome,
                    len(books),
                    failed,
                    spent() - before,
                    emailed,
                    int(email_failed),
                    run_id,
                ),
            )
            connection.commit()
    logger.info(
        "Daily check: %s, %d books, %d failed, %d Open Library requests, %d emailed",
        outcome,
        len(books),
        failed,
        spent() - before,
        emailed,
    )
    return run_id


def tick(
    connect: ConnectFn,
    search: SearchFn,
    enrich: enrichment.EnrichFn,
    spent: SpentFn,
    now: datetime,
    notify: NotifyFn | None = None,
) -> int | None:
    """Run the check if it is due. Returns the run's id, or `None`."""
    with closing(connect()) as connection:
        owed = due(connection, now)
    return run(connect, search, enrich, spent, notify) if owed else None


def start(
    connect: ConnectFn,
    search: SearchFn,
    enrich: enrichment.EnrichFn,
    spent: SpentFn,
    *,
    notify: NotifyFn | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> threading.Thread:
    """Start the thread that runs the check when it is due."""

    def loop() -> None:
        while True:
            try:
                tick(connect, search, enrich, spent, now(), notify)
            except Exception:
                # A run that raised has recorded itself as failed, if it got
                # as far as starting. Either way the thread lives to try again.
                logger.exception("Daily check could not run")
            time.sleep(POLL_SECONDS)

    thread = threading.Thread(target=loop, name="daily-check", daemon=True)
    thread.start()
    return thread


@dataclass(frozen=True, slots=True)
class Status:
    """Something wrong with the daily check, as the want list says it."""

    #: failed, throttled or missed.
    kind: str
    #: When the last run finished, if one ever has.
    finished: datetime | None
    books: int = 0
    failed: int = 0

    @property
    def label(self) -> str:
        return {
            "failed": "Daily check failed",
            "throttled": "Daily check throttled",
            "missed": "Daily check didn't run",
        }[self.kind]

    @property
    def explanation(self) -> str:
        when = _local(self.finished)
        if self.kind == "failed":
            return (
                f"The check that finished {when} couldn't search {self.failed} "
                f"of {self.books} books. Update checks them now."
            )
        if self.kind == "throttled":
            return (
                f"The check that finished {when} used up the day's Open Library "
                "requests, so some copies are waiting to be examined."
            )
        if self.finished is None:
            return "No daily check has run yet. It runs at 7am New York time."
        return f"No daily check has finished since {when}. It runs at 7am."


def _local(moment: datetime | None) -> str:
    if moment is None:
        return ""
    local = moment.astimezone(ZONE)
    hour = local.strftime("%I:%M%p").lstrip("0").lower()
    return f"{local.strftime('%b')} {local.day} at {hour}"


def status(connection: sqlite3.Connection, now: datetime) -> Status | None:
    """What the want list should say about the daily check, or `None` when
    there is nothing to say. Silence is the normal case: each row already
    says when its book was checked."""
    latest = connection.execute(
        "SELECT finished_at, outcome, books, failed FROM daily_run "
        "WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    finished = _read(latest["finished_at"]) if latest else None
    if finished is None or now - finished > OVERDUE:
        going = connection.execute(
            "SELECT 1 FROM daily_run WHERE finished_at IS NULL AND started_at >= ?",
            (_stored(now - ABANDONED),),
        ).fetchone()
        if going:
            return None
        return Status("missed", finished)
    if latest["outcome"] in ("failed", "throttled"):
        return Status(latest["outcome"], finished, latest["books"], latest["failed"])
    return None

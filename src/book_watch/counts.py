"""What the app counts, for Fly's Prometheus and Grafana (S78, #275).

Counts of events are moved by `monitoring`, the module that writes each event's
log line, so a line and its count never disagree. Counts of state are read
from the database when Fly collects them: the cheap ones each time, what's
found once every 15 minutes, and the test write at most once a minute.

Names and labels are in `docs/rules/monitoring.md`. No label holds a book's
title or id: a label with a value per book makes the count grow with the
list, and Fly drops counts that do.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing
from pathlib import Path

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    ProcessCollector,
    disable_created_metrics,
    start_http_server,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

ConnectFn = Callable[[], sqlite3.Connection]

#: Where Fly collects from, named in `fly.toml`'s `[metrics]`. Not one of the
#: ports `[http_service]` sends outside traffic to.
PORT = 9091

#: How often what's found is worked out again. It changes only when a check
#: runs, and working it out is the want list's work over every book.
FOUND_EVERY = 15 * 60
#: How often the test write is made at most.
WRITE_EVERY = 60

logger = logging.getLogger(__name__)

# A `_created` series beside every count doubles the series and says nothing
# Grafana's rate and increase need.
disable_created_metrics()

REGISTRY = CollectorRegistry()
# The process's start time among them, so Grafana can count restarts.
ProcessCollector(registry=REGISTRY)

_SECONDS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 300, 900)

calls = Counter(
    "bookwatch_calls",
    "Requests to an outside service.",
    ["service", "endpoint", "trigger", "outcome", "reason"],
    registry=REGISTRY,
)
call_seconds = Histogram(
    "bookwatch_call_seconds",
    "How long a request to an outside service took.",
    ["service", "endpoint"],
    buckets=_SECONDS,
    registry=REGISTRY,
)
checks = Counter(
    "bookwatch_checks",
    "Marketplace checks of a book.",
    ["marketplace", "trigger", "outcome"],
    registry=REGISTRY,
)
check_copies = Counter(
    "bookwatch_check_copies",
    "Copies a marketplace check returned.",
    ["marketplace"],
    registry=REGISTRY,
)
check_new_copies = Counter(
    "bookwatch_check_new_copies",
    "Copies a marketplace check returned that it had not seen before.",
    ["marketplace"],
    registry=REGISTRY,
)
checks_full = Counter(
    "bookwatch_checks_full",
    "Marketplace checks whose page came back full, so copies past it went unseen.",
    ["marketplace"],
    registry=REGISTRY,
)
jobs = Counter(
    "bookwatch_jobs",
    "Runs of a job the app does on its own.",
    ["name", "outcome"],
    registry=REGISTRY,
)
job_seconds = Histogram(
    "bookwatch_job_seconds",
    "How long a job took.",
    ["name"],
    buckets=_SECONDS,
    registry=REGISTRY,
)
pages = Counter(
    "bookwatch_pages",
    "Requests to the app.",
    ["route", "status"],
    registry=REGISTRY,
)
page_seconds = Histogram(
    "bookwatch_page_seconds",
    "How long the app took to answer.",
    ["route"],
    buckets=_SECONDS,
    registry=REGISTRY,
)
actions = Counter(
    "bookwatch_actions",
    "Things done in the app.",
    ["name"],
    registry=REGISTRY,
)
price_moves = Counter(
    "bookwatch_price_moves",
    "Copies whose delivered price a check moved.",
    ["marketplace", "direction"],
    registry=REGISTRY,
)


class State(Collector):
    """Counts of state, read from the database when Fly collects them.

    A collection that can't read the database publishes `db_readable 0` and
    nothing else from it, so the counts the app keeps in memory still arrive.
    """

    def __init__(
        self,
        connect: ConnectFn,
        path: Callable[[], Path],
        version: Callable[[], str],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._connect = connect
        self._path = path
        self._version = version
        self._clock = clock
        self._lock = threading.Lock()
        self._found: list[Metric] = []
        self._found_at: float | None = None
        self._wrote_at: float | None = None
        self._last_good_write: float | None = None
        self._writable = True

    def collect(self) -> Iterator[Metric]:
        version = GaugeMetricFamily(
            "bookwatch_version_info", "The version deployed.", labels=["version"]
        )
        version.add_metric([self._version()], 1)
        yield version
        with self._lock:
            try:
                with closing(self._connect()) as connection:
                    self._write(connection)
                    fresh = list(self._read(connection))
                    found = self._found_now(connection)
            except Exception as exc:
                logger.warning("The counts could not read the database: %s", exc)
                yield _gauge("bookwatch_db_readable", "Whether the counts read it.", 0)
                return
        yield _gauge("bookwatch_db_readable", "Whether the counts read it.", 1)
        yield from fresh
        yield from found
        yield from self._health()

    def _write(self, connection: sqlite3.Connection) -> None:
        now = self._clock()
        if self._wrote_at is not None and now - self._wrote_at < WRITE_EVERY:
            return
        self._wrote_at = now
        try:
            connection.execute(
                "INSERT INTO test_write (id, at) VALUES (1, datetime('now')) "
                "ON CONFLICT (id) DO UPDATE SET at = excluded.at"
            )
            connection.commit()
        except sqlite3.Error as exc:
            self._writable = False
            logger.error("The test write failed: %s", exc)
            return
        self._writable = True
        self._last_good_write = now

    def _health(self) -> Iterator[Metric]:
        yield _gauge(
            "bookwatch_db_writable",
            "Whether the last test write reached the disk.",
            int(self._writable),
        )
        if self._last_good_write is not None:
            yield _gauge(
                "bookwatch_db_last_write_timestamp_seconds",
                "When a test write last reached the disk.",
                self._last_good_write,
            )
        try:
            size = sum(
                os.path.getsize(part)
                for part in (str(self._path()), f"{self._path()}-wal")
                if os.path.exists(part)
            )
        except OSError:
            return
        yield _gauge("bookwatch_db_bytes", "The database file's size.", size)

    def _read(self, connection: sqlite3.Connection) -> Iterator[Metric]:
        """The cheap reads, made at every collection."""
        spent = connection.execute(
            "SELECT COUNT(*) FROM openlibrary_call WHERE at > datetime('now', '-1 day')"
        ).fetchone()[0]
        yield _gauge(
            "bookwatch_openlibrary_calls_last_day",
            "Open Library requests in the last 24 hours, from the ledger the "
            "app enforces its 500 from.",
            spent,
        )
        run = connection.execute(
            "SELECT * FROM daily_run WHERE finished_at IS NOT NULL "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if run is None:
            return
        finished = GaugeMetricFamily(
            "bookwatch_daily_last_finished_timestamp_seconds",
            "When the last daily check finished, and how it went.",
            labels=["outcome"],
        )
        finished.add_metric([run["outcome"] or ""], _epoch(run["finished_at"]))
        yield finished
        last = GaugeMetricFamily(
            "bookwatch_daily_last",
            "The last daily check's numbers.",
            labels=["count"],
        )
        for name in (
            "books",
            "failed",
            "openlibrary_spent",
            "emailed",
            "email_failed",
            "abebooks_read",
            "abebooks_failed",
            "abebooks_unordered",
        ):
            last.add_metric([name], run[name])
        yield last

    def _found_now(self, connection: sqlite3.Connection) -> list[Metric]:
        """What's found, worked out again only every `FOUND_EVERY`."""
        now = self._clock()
        if self._found_at is None or now - self._found_at >= FOUND_EVERY:
            self._found = found(connection)
            self._found_at = now
        return self._found


def found(connection: sqlite3.Connection) -> list[Metric]:
    """What the want list shows, counted: read from the store as it reads it."""
    from book_watch import copies, wantlist

    books = wantlist.all_books(connection)
    listed: dict[str, int] = {}
    under: dict[str, int] = {}
    with_one_under = 0
    for book in books:
        here, _ = copies.populations(connection, book, scope="us")
        certain = [one for one in here if one.tier == "certain"]
        for one in certain:
            listed[one.marketplace] = listed.get(one.marketplace, 0) + 1
            if one.against(book.will_pay) == "under":
                under[one.marketplace] = under.get(one.marketplace, 0) + 1
        with_one_under += any(one.against(book.will_pay) == "under" for one in certain)
    bought = connection.execute("SELECT COUNT(*) FROM purchase").fetchone()[0]

    copies_listed = GaugeMetricFamily(
        "bookwatch_copies_listed",
        "Copies certainly a book on the list, listed now from US sellers.",
        labels=["marketplace"],
    )
    copies_under = GaugeMetricFamily(
        "bookwatch_copies_under_limit",
        "Of those, copies under their book's limit.",
        labels=["marketplace"],
    )
    for marketplace in ("ebay", "abebooks"):
        copies_listed.add_metric([marketplace], listed.get(marketplace, 0))
        copies_under.add_metric([marketplace], under.get(marketplace, 0))
    return [
        _gauge("bookwatch_books", "Books on the want list.", len(books)),
        _gauge(
            "bookwatch_books_under_limit",
            "Books with a copy under their limit.",
            with_one_under,
        ),
        _gauge("bookwatch_books_bought", "Books marked bought.", bought),
        copies_listed,
        copies_under,
    ]


def _gauge(name: str, documentation: str, value: float) -> GaugeMetricFamily:
    return GaugeMetricFamily(name, documentation, value=value)


def _epoch(stored: str) -> float:
    from datetime import UTC, datetime

    moment = datetime.fromisoformat(stored)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def serve(
    connect: ConnectFn,
    path: Callable[[], Path],
    version: Callable[[], str],
    port: int = PORT,
) -> None:
    """Start serving the counts for Fly to collect, on a thread of their own.

    A port that can't be opened costs the counts and nothing else: the app,
    and the eBay compliance endpoint with it, must start regardless.
    """
    REGISTRY.register(State(connect, path, version))
    try:
        start_http_server(port, registry=REGISTRY)
    except OSError as exc:
        logger.error("The counts could not be served on port %d: %s", port, exc)

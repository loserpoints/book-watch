"""Tests for the counts Fly collects (S78, docs/rules/monitoring.md).

Counts of events move with their log lines, from the same helpers. Counts of
state are read from the database, what's found only every 15 minutes, and a
test write that can't reach the disk publishes 0.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import counts, db, monitoring, purchases, sweeps, wantlist
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import Listing, Money
from book_watch.web import listings as listings_module
from book_watch.web.page_lines import PageLines

ISBN = "9780099448396"


def value(metric: str, /, **labels: str) -> float:
    return counts.REGISTRY.get_sample_value(metric, labels) or 0.0


# --- counts of events --------------------------------------------------------


def test_a_call_is_counted_with_the_words_of_its_line():
    labels = {
        "service": "ebay",
        "endpoint": "search",
        "trigger": "recheck",
        "outcome": "failed",
        "reason": "down",
    }
    before = value("bookwatch_calls_total", **labels)

    with (
        pytest.raises(EbayError),
        monitoring.started_by("recheck"),
        monitoring.call("ebay", "search"),
    ):
        monitoring.call_answered(503)
        raise EbayError("eBay said 503")

    assert value("bookwatch_calls_total", **labels) == before + 1
    assert value("bookwatch_call_seconds_count", service="ebay", endpoint="search")


def test_a_call_with_no_reason_is_counted_with_an_empty_one():
    labels = {
        "service": "resend",
        "endpoint": "send",
        "trigger": "unknown",
        "outcome": "ok",
        "reason": "",
    }
    before = value("bookwatch_calls_total", **labels)

    with monitoring.call("resend", "send"):
        pass

    assert value("bookwatch_calls_total", **labels) == before + 1


def test_a_check_counts_its_copies_the_new_ones_and_a_full_page():
    before = {
        name: value(name, marketplace="abebooks")
        for name in (
            "bookwatch_check_copies_total",
            "bookwatch_check_new_copies_total",
            "bookwatch_checks_full_total",
        )
    }
    checks = value(
        "bookwatch_checks_total", marketplace="abebooks", trigger="daily", outcome="ok"
    )

    with monitoring.started_by("daily"), monitoring.check("abebooks"):
        monitoring.check_saw(copies=30, new=4, full=True)

    assert value("bookwatch_check_copies_total", marketplace="abebooks") == (
        before["bookwatch_check_copies_total"] + 30
    )
    assert value("bookwatch_check_new_copies_total", marketplace="abebooks") == (
        before["bookwatch_check_new_copies_total"] + 4
    )
    assert value("bookwatch_checks_full_total", marketplace="abebooks") == (
        before["bookwatch_checks_full_total"] + 1
    )
    assert value(
        "bookwatch_checks_total", marketplace="abebooks", trigger="daily", outcome="ok"
    ) == (checks + 1)


def test_a_job_and_an_action_are_counted():
    jobs = value("bookwatch_jobs_total", name="email", outcome="skipped")
    actions = value("bookwatch_actions_total", name="bought")

    with monitoring.job("email") as sending:
        sending.outcome = "skipped"
    monitoring.action("bought", book=1, title="Crash")

    assert value("bookwatch_jobs_total", name="email", outcome="skipped") == jobs + 1
    assert value("bookwatch_actions_total", name="bought") == actions + 1


def a_listing(n: int, price: str) -> Listing:
    return Listing(
        item_id=f"v1|{n}|0",
        title="Crash by J. G. Ballard",
        price=Money(Decimal(price), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        condition="Good",
        seller="seller",
        shipping_cost=Money(Decimal("2.00"), "USD"),
        thumbnail_url=None,
        listing_date=datetime(2026, 9, 1, tzinfo=UTC),
    )


@pytest.fixture
def path(tmp_path) -> Path:
    return tmp_path / "book-watch.db"


@pytest.fixture
def connect(path):
    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    return connect


def test_a_price_a_check_moved_is_counted_by_which_way(connect):
    down = value("bookwatch_price_moves_total", marketplace="ebay", direction="down")
    up = value("bookwatch_price_moves_total", marketplace="ebay", direction="up")
    with closing(connect()) as connection:
        work = wantlist.add(connection, ISBN, "Crash").work_id
        sweeps.store(connection, work, [a_listing(1, "9.00"), a_listing(2, "5.00")])
        sweeps.store(connection, work, [a_listing(1, "7.00"), a_listing(2, "5.00")])
        sweeps.store(connection, work, [a_listing(1, "7.50"), a_listing(2, "4.00")])

    assert value(
        "bookwatch_price_moves_total", marketplace="ebay", direction="down"
    ) == (down + 2)
    assert value("bookwatch_price_moves_total", marketplace="ebay", direction="up") == (
        up + 1
    )


def test_a_page_is_counted_by_its_route_never_its_address(connect):
    with closing(connect()) as connection:
        wantlist.add(connection, ISBN, "Crash")
        connection.commit()
    app = FastAPI()
    # Examining copies stubbed too, or it falls back to the real one, which
    # needs eBay's keys: present where this was written, absent in CI.
    app.include_router(
        listings_module.build_router(
            lambda query, limit, **_: [], connect, enrich=lambda work_id: None
        )
    )
    app.add_middleware(PageLines)
    before = value("bookwatch_pages_total", route="/book/{book_id}", status="200")

    TestClient(app).get("/book/1")

    assert value("bookwatch_pages_total", route="/book/{book_id}", status="200") == (
        before + 1
    )
    assert not value("bookwatch_pages_total", route="/book/1", status="200")


# --- counts of state ---------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def a_state(connect, path, clock=None) -> counts.State:
    return counts.State(connect, lambda: path, lambda: "abc123", clock or Clock())


def collected(state: counts.State) -> dict[str, dict[tuple, float]]:
    """Each metric's samples, by their labels' values."""
    return {
        metric.name: {
            tuple(sample.labels.values()): sample.value for sample in metric.samples
        }
        for metric in state.collect()
    }


def seeded(connect) -> None:
    """Two books with copies certainly theirs, one bought, a daily run and
    Open Library calls in and out of the last day."""
    with closing(connect()) as connection:
        crash = wantlist.add(connection, ISBN, "Crash")
        sweeps.store(
            connection, crash.work_id, [a_listing(1, "5.00"), a_listing(2, "15.00")]
        )
        for n in (1, 2):
            connection.execute(
                "INSERT INTO listing_declaration (marketplace, item_id, isbn) "
                "VALUES ('ebay', ?, ?)",
                (f"v1|{n}|0", ISBN),
            )
        wantlist.set_ceiling(connection, crash.id, "10", "USD")
        wantlist.add(connection, "9780141182803", "Stoner")
        gone = wantlist.add(connection, "9780140449136", "The Odyssey")
        purchases.buy(
            connection,
            gone.id,
            paid=Decimal("6.00"),
            currency="USD",
            marketplace="ebay",
            shop=None,
            bought_on=date(2026, 10, 1),
        )
        connection.executemany(
            "INSERT INTO openlibrary_call (endpoint, at) VALUES (?, ?)",
            [
                ("/isbn", "2000-01-01 00:00:00"),
                ("/isbn", datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")),
            ],
        )
        connection.execute(
            "INSERT INTO daily_run (started_at, finished_at, outcome, books, failed,"
            " emailed) VALUES ('2026-10-08 11:00:00', '2026-10-08 11:04:00', 'ok',"
            " 2, 0, 1)"
        )
        connection.commit()


def test_whats_found_is_counted_as_the_want_list_reads_it(connect, path):
    seeded(connect)

    found = collected(a_state(connect, path))

    assert found["bookwatch_books"] == {(): 2}
    assert found["bookwatch_books_bought"] == {(): 1}
    assert found["bookwatch_books_under_limit"] == {(): 1}
    assert found["bookwatch_copies_listed"] == {("ebay",): 2, ("abebooks",): 0}
    assert found["bookwatch_copies_under_limit"] == {("ebay",): 1, ("abebooks",): 0}


def test_open_library_and_the_last_daily_check_are_read_from_the_database(
    connect, path
):
    seeded(connect)

    found = collected(a_state(connect, path))

    assert found["bookwatch_openlibrary_calls_last_day"] == {(): 1}
    assert found["bookwatch_daily_last_finished_timestamp_seconds"] == {
        ("ok",): datetime(2026, 10, 8, 11, 4, tzinfo=UTC).timestamp()
    }
    assert found["bookwatch_daily_last"][("books",)] == 2
    assert found["bookwatch_daily_last"][("emailed",)] == 1
    assert found["bookwatch_version_info"] == {("abc123",): 1}
    assert found["bookwatch_db_bytes"][()] > 0


def test_whats_found_is_worked_out_again_only_every_fifteen_minutes(connect, path):
    seeded(connect)
    clock = Clock()
    state = a_state(connect, path, clock)
    collected(state)
    with closing(connect()) as connection:
        wantlist.add(connection, "9780679734505", "Pale Fire")
        connection.commit()

    clock.now += counts.FOUND_EVERY - 1
    assert collected(state)["bookwatch_books"] == {(): 2}
    clock.now += 1
    assert collected(state)["bookwatch_books"] == {(): 3}


def test_the_test_write_reaches_the_disk_at_most_once_a_minute(connect, path):
    clock = Clock()
    state = a_state(connect, path, clock)

    first = collected(state)
    with closing(connect()) as connection:
        written = connection.execute("SELECT at FROM test_write").fetchall()
    clock.now += 30
    collected(state)

    assert len(written) == 1
    assert first["bookwatch_db_writable"] == {(): 1}
    assert first["bookwatch_db_last_write_timestamp_seconds"] == {(): 1_000_000.0}
    assert collected(state)["bookwatch_db_last_write_timestamp_seconds"] == {
        (): 1_000_000.0
    }


class _Full:
    """A connection whose writes fail as a full disk's do."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(self, sql, *args):
        if sql.lstrip().upper().startswith("INSERT"):
            raise sqlite3.OperationalError("database or disk is full")
        return self._connection.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_a_write_that_cant_reach_the_disk_publishes_0_and_says_so(
    connect, path, caplog
):
    state = a_state(lambda: _Full(connect()), path)

    with caplog.at_level(logging.ERROR, logger="book_watch.counts"):
        found = collected(state)

    assert found["bookwatch_db_writable"] == {(): 0}
    assert "bookwatch_db_last_write_timestamp_seconds" not in found
    assert "The test write failed: database or disk is full" in caplog.text


def test_a_database_it_cant_read_still_lets_the_other_counts_through(path):
    def broken():
        raise sqlite3.OperationalError("unable to open database file")

    found = collected(a_state(broken, path))

    assert found["bookwatch_db_readable"] == {(): 0}
    assert "bookwatch_version_info" in found
    assert "bookwatch_books" not in found


def test_its_own_migration_adds_the_test_write_table(connect):
    with closing(connect()) as connection:
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "test_write" in applied
    assert (db.MIGRATIONS_DIR / "030_a_test_write.sql").exists()


def test_building_the_app_opens_no_port(monkeypatch):
    from book_watch.config import DeletionEndpointConfig
    from book_watch.web.app import create_app

    def refuse(*args, **kwargs):
        raise AssertionError("create_app must not serve the counts")

    monkeypatch.setattr(counts, "serve", refuse)
    monkeypatch.setattr(counts, "start_http_server", refuse)

    create_app(
        DeletionEndpointConfig(
            verification_token="a" * 32,
            endpoint_url="https://book-watch-alan.fly.dev/ebay/deletion",
        )
    )


def test_a_port_it_cant_open_costs_the_counts_and_not_the_app(monkeypatch, caplog):
    def taken(*args, **kwargs):
        raise OSError("Address already in use")

    monkeypatch.setattr(counts, "start_http_server", taken)
    monkeypatch.setattr(counts.REGISTRY, "register", lambda collector: None)

    with caplog.at_level(logging.ERROR, logger="book_watch.counts"):
        counts.serve(lambda: None, lambda: Path("x"), lambda: "v")

    assert "could not be served on port 9091: Address already in use" in caplog.text


def test_the_disk_the_database_is_on_is_measured(connect, path):
    found = collected(a_state(connect, path))

    size = found["bookwatch_volume_size_bytes"][()]
    free = found["bookwatch_volume_free_bytes"][()]
    assert 0 < free <= size

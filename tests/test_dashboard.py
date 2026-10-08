"""Tests for the Grafana dashboard (S79).

A count renamed in the app would leave its panel silently empty, so every
query must name a count the app publishes. And the file imported into Grafana
must be the one the script writes.
"""

import importlib.util
import json
import re
from contextlib import closing
from pathlib import Path

from prometheus_client.core import CounterMetricFamily, HistogramMetricFamily

from book_watch import counts, db, monitoring, wantlist

ROOT = Path(__file__).resolve().parent.parent


def builder():
    spec = importlib.util.spec_from_file_location(
        "build_dashboard", ROOT / "scripts" / "build_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def published(tmp_path) -> set[str]:
    """Every series name the app can publish, as Prometheus stores it."""
    names: set[str] = set()
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    with closing(connect()) as connection:
        wantlist.add(connection, "9780099448396", "Crash")
        connection.execute(
            "INSERT INTO daily_run (finished_at, outcome) "
            "VALUES (datetime('now'), 'ok')"
        )
        connection.commit()
    state = counts.State(connect, lambda: path, lambda: "v")
    for metric in [*counts.REGISTRY.collect(), *state.collect()]:
        if isinstance(metric, CounterMetricFamily) or metric.type == "counter":
            names.add(f"{metric.name}_total")
        elif isinstance(metric, HistogramMetricFamily) or metric.type == "histogram":
            names |= {f"{metric.name}_{part}" for part in ("bucket", "sum", "count")}
        else:
            names.add(metric.name)
    return names


def queries() -> list[str]:
    board = json.loads((ROOT / "grafana" / "book-watch.json").read_text())

    def walk(panels):
        for panel in panels:
            yield panel
            yield from walk(panel.get("panels", []))

    return [
        query["expr"]
        for panel in walk(board["panels"])
        for query in panel.get("targets", [])
    ]


def test_every_query_names_a_count_the_app_publishes(tmp_path):
    # So every counter has been moved at least once and is listed.
    with monitoring.call("resend", "send"):
        pass
    available = published(tmp_path)

    asked = {
        name
        for expr in queries()
        for name in re.findall(r"\b(?:bookwatch|process)_\w+", expr)
    }

    assert asked
    assert asked - available == set()


def test_every_query_is_limited_to_this_app():
    for expr in queries():
        for selector in re.findall(r"\b(?:bookwatch|process)_\w+\{([^}]*)\}", expr):
            assert 'app="$app"' in selector, expr


def test_the_file_is_what_the_script_writes():
    assert (ROOT / "grafana" / "book-watch.json").read_text() == builder().render()

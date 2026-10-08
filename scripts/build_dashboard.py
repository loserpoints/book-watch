"""Write the Grafana dashboard, grafana/book-watch.json, from this file (S79).

    uv run python scripts/build_dashboard.py

The dashboard is imported into Fly's Grafana by hand (runbook). It reads only
the counts in docs/rules/monitoring.md, and a test checks every query names
one the app publishes and that the file matches what this writes.

Rows run from what to check first, on a phone, to what to dig into: is it
working, the limits, the daily check, eBay and AbeBooks side by side, calls,
what's found, the app. The first two are open; the rest open on a tap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent.parent / "grafana" / "book-watch.json"
APP = 'app="$app"'

# One color per entity, everywhere: categorical slots validated as a set
# against Grafana's dark surface (dataviz validator, dark mode).
SERVICE = {
    "ebay": "#3987e5",
    "abebooks": "#d95926",
    "openlibrary": "#199e70",
    "resend": "#c98500",
}
# Status colors, reserved for how something went and for limits.
GOOD, WARNING, SERIOUS, CRITICAL, NEUTRAL = (
    "#0ca30c",
    "#fab219",
    "#ec835a",
    "#d03b3b",
    "#8e8e8e",
)
OUTCOME = {
    "ok": GOOD,
    "empty": NEUTRAL,
    "skipped": WARNING,
    "throttled": WARNING,
    "failed": CRITICAL,
}

_ids = iter(range(1, 1000))


def target(expr: str, legend: str = "", ref: str = "A") -> dict[str, Any]:
    return {
        "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
        "range": True,
    }


def thresholds(*steps: tuple[float | None, str]) -> dict[str, Any]:
    return {
        "mode": "absolute",
        "steps": [{"value": value, "color": color} for value, color in steps],
    }


def colored(names: dict[str, str]) -> list[dict[str, Any]]:
    """Fix each series' color by its name, so it never moves with rank."""
    return [
        {
            "matcher": {"id": "byName", "options": name},
            "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": color}}
            ],
        }
        for name, color in names.items()
    ]


def stat(
    title: str,
    expr: str,
    *,
    unit: str = "short",
    steps: tuple[tuple[float | None, str], ...] = ((None, NEUTRAL),),
    mappings: list[dict[str, Any]] | None = None,
    text: str = "value",
    legend: str = "",
    description: str = "",
    decimals: int | None = None,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "unit": unit,
        "thresholds": thresholds(*steps),
        "color": {"mode": "thresholds"},
        "mappings": mappings or [],
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    return {
        "type": "stat",
        "title": title,
        "description": description,
        "targets": [target(expr, legend)],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "background",
            "graphMode": "none",
            "textMode": text,
            "justifyMode": "center",
            "orientation": "auto",
        },
    }


def gauge(
    title: str, expr: str, limit: float, warn: float, bad: float, description: str
) -> dict[str, Any]:
    return {
        "type": "gauge",
        "title": title,
        "description": description,
        "targets": [target(expr)],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "decimals": 0,
                "min": 0,
                "max": limit,
                "thresholds": thresholds(
                    (None, GOOD), (warn, WARNING), (bad, CRITICAL)
                ),
                "color": {"mode": "thresholds"},
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showThresholdMarkers": True,
            "showThresholdLabels": False,
        },
    }


def series(
    title: str,
    *targets: dict[str, Any],
    unit: str = "short",
    colors: dict[str, str] | None = None,
    bars: bool = False,
    interval: str | None = None,
    stacked: bool = False,
    description: str = "",
    limit: float | None = None,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "unit": unit,
        "custom": {
            "drawStyle": "bars" if bars else "line",
            "lineWidth": 2,
            "fillOpacity": 80 if bars else 0,
            "pointSize": 8,
            "showPoints": "auto",
            "spanNulls": False,
            "stacking": {"mode": "normal" if stacked else "none", "group": "A"},
            "axisSoftMin": 0,
            "barAlignment": -1,
        },
        "color": {"mode": "palette-classic"},
    }
    if limit is not None:
        # The limit as a dashed line, so a series is read against it.
        defaults["thresholds"] = thresholds((None, GOOD), (limit, CRITICAL))
        defaults["custom"]["thresholdsStyle"] = {"mode": "dashed"}
    panel: dict[str, Any] = {
        "type": "timeseries",
        "title": title,
        "description": description,
        "targets": list(targets),
        "fieldConfig": {"defaults": defaults, "overrides": colored(colors or {})},
        "options": {
            "legend": {
                "showLegend": True,
                "displayMode": "list",
                "placement": "bottom",
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }
    if interval:
        panel["interval"] = interval
    return panel


def per_hour(metric: str, by: str, where: str = "") -> str:
    match = f"{APP},{where}" if where else APP
    return f"sum by ({by}) (increase({metric}{{{match}}}[1h]))"


def per_day(metric: str, by: str, where: str = "") -> str:
    match = f"{APP},{where}" if where else APP
    return f"sum by ({by}) (increase({metric}{{{match}}}[1d]))"


def p95(metric: str, by: str) -> str:
    return (
        f"histogram_quantile(0.95, sum by ({by}, le) "
        f"(rate({metric}_bucket{{{APP}}}[1h])))"
    )


YES_NO = [
    {
        "type": "value",
        "options": {
            "0": {"text": "No", "color": CRITICAL, "index": 0},
            "1": {"text": "Yes", "color": GOOD, "index": 1},
        },
    }
]

DAY = 24 * 3600


def rows() -> list[tuple[str, bool, list[tuple[dict[str, Any], int, int]]]]:
    """Each row: its title, whether it starts open, and its panels with
    their width and height on Grafana's 24-column grid."""
    working = [
        (
            stat(
                "Last daily check",
                "time() - max("
                f"bookwatch_daily_last_finished_timestamp_seconds{{{APP}}})",
                unit="s",
                steps=((None, GOOD), (DAY + 3600, WARNING), (DAY + 3 * 3600, CRITICAL)),
                description="How long ago the last daily check finished. It runs at "
                "7am New York time.",
                decimals=0,
            ),
            6,
            4,
        ),
        (
            stat(
                "How it went",
                "max by (outcome) "
                f"(bookwatch_daily_last_finished_timestamp_seconds{{{APP}}})",
                text="name",
                legend="{{outcome}}",
                mappings=[],
                description="The last daily check's outcome: ok, throttled or failed.",
            ),
            6,
            4,
        ),
        (
            stat(
                "Books it couldn't check",
                f'max(bookwatch_daily_last{{{APP},count="failed"}})',
                steps=((None, GOOD), (1, CRITICAL)),
                description="Books whose eBay search failed in the last daily check. "
                "Search the logs for trigger=daily outcome=failed.",
            ),
            6,
            4,
        ),
        (
            stat(
                "Database can be written",
                f"min(bookwatch_db_writable{{{APP}}})",
                mappings=YES_NO,
                steps=((None, CRITICAL), (1, GOOD)),
                description="Whether the last test write reached the disk. It is "
                "made at most once a minute.",
            ),
            6,
            4,
        ),
        (
            stat(
                "Disk free",
                f"min(bookwatch_volume_free_bytes{{{APP}}}) / "
                f"min(bookwatch_volume_size_bytes{{{APP}}})",
                unit="percentunit",
                steps=((None, CRITICAL), (0.1, WARNING), (0.25, GOOD)),
                description="Space free on the volume the database is on.",
                decimals=0,
            ),
            8,
            4,
        ),
        (
            stat(
                "Restarts, last day",
                f"sum(changes(process_start_time_seconds{{{APP}}}[1d]))",
                steps=((None, GOOD), (3, WARNING)),
                description="Each deploy restarts the app. More than a few a day "
                "without deploys means it is crashing.",
            ),
            8,
            4,
        ),
        (
            stat(
                "Errors, last day",
                f'round(sum(increase(bookwatch_pages_total{{{APP},status=~"5.."}}[1d])))',
                steps=((None, GOOD), (1, CRITICAL)),
                description="Pages answered 5xx. A 500 is a crash; search the logs "
                "for event=page status=500.",
            ),
            8,
            4,
        ),
    ]

    limits = [
        (
            gauge(
                "eBay calls, last day",
                f'round(sum(increase(bookwatch_calls_total{{{APP},service="ebay"}}[1d])))',
                5000,
                3000,
                4500,
                "Against eBay's 5,000 a day. Read from the counts, so a restart can "
                "lose a few seconds of calls.",
            ),
            8,
            6,
        ),
        (
            gauge(
                "Open Library calls, last day",
                f"max(bookwatch_openlibrary_calls_last_day{{{APP}}})",
                500,
                300,
                450,
                "Against the app's own limit of 500 in 24 hours, from the ledger it "
                "enforces it from.",
            ),
            8,
            6,
        ),
        (
            gauge(
                "Emails sent, last day",
                "round(sum(increase(bookwatch_calls_total"
                f'{{{APP},service="resend",outcome="ok"}}[1d])))',
                3,
                2,
                2,
                "The app sends one email a morning at most.",
            ),
            8,
            6,
        ),
    ]

    daily = [
        (
            series(
                "Daily checks",
                target(
                    per_hour("bookwatch_jobs_total", "outcome", 'name="daily"'),
                    "{{outcome}}",
                ),
                bars=True,
                interval="1h",
                stacked=True,
                colors=OUTCOME,
                description="Each run, by how it went.",
            ),
            12,
            8,
        ),
        (
            series(
                "Morning email",
                target(
                    per_hour("bookwatch_jobs_total", "outcome", 'name="email"'),
                    "{{outcome}}",
                ),
                bars=True,
                interval="1h",
                stacked=True,
                colors=OUTCOME,
                description="Skipped with reason=setup means a Resend setting is "
                "missing on Fly.",
            ),
            12,
            8,
        ),
        (
            series(
                "How long each run took",
                target(
                    f'increase(bookwatch_job_seconds_sum{{{APP},name="daily"}}[1h]) / '
                    f'increase(bookwatch_job_seconds_count{{{APP},name="daily"}}[1h])',
                    "daily check",
                ),
                unit="s",
                interval="1h",
            ),
            12,
            8,
        ),
        (
            series(
                "The last run's numbers",
                target(f"max by (count) (bookwatch_daily_last{{{APP}}})", "{{count}}"),
                description="Books checked, failed, emailed, and AbeBooks' reads, "
                "failures and pages out of price order.",
            ),
            12,
            8,
        ),
    ]

    marketplaces = {"ebay": SERVICE["ebay"], "abebooks": SERVICE["abebooks"]}
    side_by_side = [
        (
            series(
                "Checks that failed",
                target(
                    per_hour(
                        "bookwatch_checks_total", "marketplace", 'outcome="failed"'
                    ),
                    "{{marketplace}}",
                ),
                bars=True,
                interval="1h",
                colors=marketplaces,
                description="Search the logs for event=check outcome=failed for why.",
            ),
            12,
            8,
        ),
        (
            series(
                "Copies returned",
                target(
                    per_hour("bookwatch_check_copies_total", "marketplace"),
                    "{{marketplace}}",
                ),
                bars=True,
                interval="1h",
                colors=marketplaces,
            ),
            12,
            8,
        ),
        (
            series(
                "New copies",
                target(
                    per_hour("bookwatch_check_new_copies_total", "marketplace"),
                    "{{marketplace}}",
                ),
                bars=True,
                interval="1h",
                colors=marketplaces,
                description="Copies a check had not seen before.",
            ),
            12,
            8,
        ),
        (
            series(
                "Full pages",
                target(
                    per_hour("bookwatch_checks_full_total", "marketplace"),
                    "{{marketplace}}",
                ),
                bars=True,
                interval="1h",
                colors=marketplaces,
                description="Checks whose page came back full, so copies past it "
                "went unseen.",
            ),
            12,
            8,
        ),
        (
            series(
                "AbeBooks pages out of price order",
                target(
                    f'max(bookwatch_daily_last{{{APP},count="abebooks_unordered"}})',
                    "abebooks",
                ),
                colors={"abebooks": SERVICE["abebooks"]},
                description="In each daily check. Climbing morning after morning "
                "means AbeBooks no longer sorts cheapest first.",
            ),
            24,
            8,
        ),
    ]

    calls = [
        (
            series(
                "Calls",
                target(per_hour("bookwatch_calls_total", "service"), "{{service}}"),
                bars=True,
                interval="1h",
                stacked=True,
                colors=SERVICE,
            ),
            12,
            8,
        ),
        (
            series(
                "Calls that failed or were skipped",
                target(
                    per_hour(
                        "bookwatch_calls_total",
                        "service, reason",
                        'outcome=~"failed|skipped"',
                    ),
                    "{{service}} {{reason}}",
                ),
                bars=True,
                interval="1h",
                stacked=True,
                description="By service and reason. Search the logs for event=call "
                "outcome=failed for each one.",
            ),
            12,
            8,
        ),
        (
            series(
                "How slow each service is (95th percentile)",
                target(p95("bookwatch_call_seconds", "service"), "{{service}}"),
                unit="s",
                colors=SERVICE,
            ),
            12,
            8,
        ),
        (
            series(
                "Open Library calls in the last 24 hours",
                target(
                    f"max(bookwatch_openlibrary_calls_last_day{{{APP}}})", "openlibrary"
                ),
                colors={"openlibrary": SERVICE["openlibrary"]},
                limit=500,
                description="The dashed line is the limit of 500.",
            ),
            12,
            8,
        ),
    ]

    found = [
        (stat("Books on the list", f"max(bookwatch_books{{{APP}}})"), 8, 4),
        (
            stat(
                "Books with a copy under their limit",
                f"max(bookwatch_books_under_limit{{{APP}}})",
            ),
            8,
            4,
        ),
        (stat("Books bought", f"max(bookwatch_books_bought{{{APP}}})"), 8, 4),
        (
            series(
                "Copies listed",
                target(
                    f"max by (marketplace) (bookwatch_copies_listed{{{APP}}})",
                    "{{marketplace}}",
                ),
                colors=marketplaces,
                description="Copies certainly a book on the list, from US sellers.",
            ),
            12,
            8,
        ),
        (
            series(
                "Copies under their limit",
                target(
                    f"max by (marketplace) (bookwatch_copies_under_limit{{{APP}}})",
                    "{{marketplace}}",
                ),
                colors=marketplaces,
            ),
            12,
            8,
        ),
        (
            series(
                "New copies a day",
                target(
                    per_day("bookwatch_check_new_copies_total", "marketplace"),
                    "{{marketplace}}",
                ),
                bars=True,
                interval="1d",
                colors=marketplaces,
            ),
            12,
            8,
        ),
        (
            series(
                "Price moves a day",
                target(
                    per_day("bookwatch_price_moves_total", "direction"), "{{direction}}"
                ),
                bars=True,
                interval="1d",
                colors={"down": SERVICE["openlibrary"], "up": SERVICE["abebooks"]},
                description="Copies whose delivered price a check moved.",
            ),
            12,
            8,
        ),
    ]

    the_app = [
        (
            series(
                "Pages",
                target(per_hour("bookwatch_pages_total", "route"), "{{route}}"),
                bars=True,
                interval="1h",
                stacked=True,
            ),
            12,
            8,
        ),
        (
            series(
                "Slowest pages (95th percentile)",
                target(p95("bookwatch_page_seconds", "route"), "{{route}}"),
                unit="s",
            ),
            12,
            8,
        ),
        (
            series(
                "Pages answered 5xx",
                target(
                    per_hour("bookwatch_pages_total", "route, status", 'status=~"5.."'),
                    "{{route}} {{status}}",
                ),
                bars=True,
                interval="1h",
            ),
            12,
            8,
        ),
        (
            series(
                "Disk",
                target(f"min(bookwatch_volume_free_bytes{{{APP}}})", "free", "A"),
                target(f"max(bookwatch_db_bytes{{{APP}}})", "database", "B"),
                unit="bytes",
            ),
            12,
            8,
        ),
        (
            stat(
                "Version",
                f"max by (version) (bookwatch_version_info{{{APP}}})",
                text="name",
                legend="{{version}}",
            ),
            12,
            4,
        ),
        (
            stat(
                "Last test write",
                f"time() - max(bookwatch_db_last_write_timestamp_seconds{{{APP}}})",
                unit="s",
                steps=((None, GOOD), (180, WARNING), (600, CRITICAL)),
                decimals=0,
            ),
            12,
            4,
        ),
    ]

    return [
        ("Is it working?", True, working),
        ("Limits", True, limits),
        ("Daily check", False, daily),
        ("eBay and AbeBooks", False, side_by_side),
        ("Calls", False, calls),
        ("What's found", False, found),
        ("The app", False, the_app),
    ]


def placed(panels: list[tuple[dict[str, Any], int, int]], y: int) -> tuple[list, int]:
    """Panels laid out left to right, wrapping at 24 columns."""
    out, x, row_height = [], 0, 0
    for panel, width, height in panels:
        if x + width > 24:
            y, x, row_height = y + row_height, 0, 0
        out.append(
            {
                **panel,
                "id": next(_ids),
                "gridPos": {"x": x, "y": y, "w": width, "h": height},
            }
        )
        x += width
        row_height = max(row_height, height)
    return out, y + row_height


def dashboard() -> dict[str, Any]:
    panels: list[dict[str, Any]] = []
    y = 0
    for title, open_, members in rows():
        laid, after = placed(members, y + 1)
        row = {
            "type": "row",
            "title": title,
            "id": next(_ids),
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
            "collapsed": not open_,
            "panels": [] if open_ else laid,
        }
        panels.append(row)
        if open_:
            panels.extend(laid)
            y = after
        else:
            y += 1
    return {
        "__inputs": [
            {
                "name": "DS_PROMETHEUS",
                "label": "Prometheus",
                "description": "Fly's Prometheus",
                "type": "datasource",
                "pluginId": "prometheus",
                "pluginName": "Prometheus",
            }
        ],
        "title": "book-watch",
        "uid": "book-watch",
        "description": "What book-watch does on its own, and what goes wrong. "
        "Built by scripts/build_dashboard.py; the counts are in "
        "docs/rules/monitoring.md.",
        "tags": ["book-watch"],
        "timezone": "America/New_York",
        "time": {"from": "now-7d", "to": "now"},
        "refresh": "5m",
        "schemaVersion": 39,
        "editable": True,
        "graphTooltip": 1,
        "templating": {
            "list": [
                {
                    "name": "app",
                    "type": "constant",
                    "query": "book-watch-alan",
                    "hide": 2,
                }
            ]
        },
        "panels": panels,
    }


def render() -> str:
    global _ids
    _ids = iter(range(1, 1000))
    return json.dumps(dashboard(), indent=2) + "\n"


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render())
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

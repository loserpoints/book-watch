"""Apply pending migrations to a copy of the database and report what changed.

    uv run python scripts/try_migrations.py copy.db

Prints each table's row count before and after, and fails when a table that
existed before has fewer rows after, or when a migration fails. Prints counts
only: the run's log is public, and the rows are not.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from book_watch import db


def counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        table: connection.execute(f'SELECT count(*) AS n FROM "{table}"').fetchone()[0]
        for table in tables
    }


def _shown(count: int | None) -> str:
    return "-" if count is None else str(count)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: try_migrations.py <copy of the database>", file=sys.stderr)
        return 2
    connection = db.connect(Path(args[0]))
    before = counts(connection)
    try:
        applied = db.migrate(connection)
    except db.MigrationError as exc:
        print(f"Migration failed: {exc}")
        return 1
    after = counts(connection)
    connection.close()

    print(f"applied    {', '.join(applied) or 'nothing'}")
    lost = []
    for table in sorted(before.keys() | after.keys()):
        was, now = before.get(table), after.get(table)
        print(f"  {table:24} {_shown(was):>7} -> {_shown(now):>7}")
        if was is not None and (now is None or now < was):
            lost.append(table)
    if lost:
        print(f"Rows lost in: {', '.join(lost)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

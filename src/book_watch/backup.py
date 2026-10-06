"""Copy the live database to a file, safely, while the app keeps running.

    python -m book_watch.backup /tmp/copy.db

Uses SQLite's own backup, so the copy is consistent even if the app writes
during it. Exists so a migration can be tried on a copy of production before
it ships: see .github/workflows/try-migrations.yml.
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from book_watch.config import load_database_path


def copy_to(source: Path, destination: Path) -> None:
    """Write a consistent copy of `source` to `destination`, replacing it."""
    destination.unlink(missing_ok=True)
    with (
        closing(sqlite3.connect(source)) as live,
        closing(sqlite3.connect(destination)) as copy,
    ):
        live.backup(copy)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m book_watch.backup <destination>", file=sys.stderr)
        return 2
    copy_to(load_database_path(use_dotenv=False), Path(args[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

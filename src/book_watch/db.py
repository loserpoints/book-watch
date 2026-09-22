"""SQLite connections and the migration runner.

Plain numbered `.sql` files applied in filename order, with a table recording
which have run. No ORM and no Alembic — decisions.md entry 3 explains why the
schema is written as SQL a person can read rather than inferred from Python
classes.

The migrations live inside the package rather than at the repository root
because that is what ships: the Dockerfile copies `src` and nothing else, so a
root-level `migrations/` directory would be missing from every container. The
templates in `web/` are located the same way for the same reason.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Records which migrations have run. Created before any of them.
LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migration (
    name       TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


class MigrationError(RuntimeError):
    """A migration failed. The database is unchanged by the one that failed."""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database, creating its parent directory if needed.

    `isolation_level=None` turns off the driver's implicit transaction
    handling so this module controls transactions explicitly, which is what
    `migrate` needs to keep each migration all-or-nothing.

    Creating the parent directory matters on a first deploy: the volume is
    mounted empty, and a missing directory would otherwise be the difference
    between an app that starts and one that does not.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    # Off by default in SQLite, per connection, and silently so — a foreign
    # key constraint that is never enforced is worse than one never written.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def pending(connection: sqlite3.Connection) -> list[Path]:
    """Migrations on disk that this database has not run, in order."""
    connection.execute(LEDGER_SCHEMA)
    done = {
        row["name"] for row in connection.execute("SELECT name FROM schema_migration")
    }
    return [f for f in sorted(MIGRATIONS_DIR.glob("*.sql")) if f.name not in done]


def migrate(connection: sqlite3.Connection) -> list[str]:
    """Apply every pending migration in order. Returns the names applied.

    Running this twice is a no-op, which is what makes it safe to call on
    every start.

    Each migration runs inside an explicit transaction together with the row
    recording it, so a failure leaves neither the change nor the record.
    SQLite can do this because its DDL is transactional — a half-applied
    `CREATE TABLE` rolls back like anything else. Most databases cannot, so
    this guarantee does not travel if the store ever changes.
    """
    applied: list[str] = []
    for migration in pending(connection):
        sql = migration.read_text()
        try:
            # executescript commits any open transaction before it starts and
            # adds no transaction control of its own, so the BEGIN has to be
            # inside the script rather than issued before it.
            connection.executescript(f"BEGIN;\n{sql}")
            connection.execute(
                "INSERT INTO schema_migration (name) VALUES (?)", (migration.name,)
            )
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            connection.execute("ROLLBACK")
            raise MigrationError(f"{migration.name} failed: {exc}") from exc
        applied.append(migration.name)
    return applied

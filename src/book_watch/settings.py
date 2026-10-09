"""The app's own settings (S83, #72; S84, #182).

The ship-to ZIP that eBay prices calculated shipping to, read by every search
when it runs, so a change applies from the next one.

The default limit, the whole-dollar amount each new book starts
with. It is a starting value, not inherited. A book copies it when added and
owns its limit from then on, so changing the default changes no book already
on the list. The books that have no limit can be given it on purpose, with
`fill`.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from decimal import Decimal, InvalidOperation

from book_watch.ebay.search import Money

#: Limits are in the one currency the app searches in.
CURRENCY = "USD"

#: Three digits at most: no book on the list is worth $1,000 to its reader.
MOST = 999

DEFAULT_LIMIT = "default_limit"
SHIP_TO = "ship_to_zip"

#: A US ZIP code, five digits. eBay prices from the first five, so the
#: four-digit extension the secret once allowed is not taken.
_ZIP = re.compile(r"\d{5}")


def whole_dollars(raw: str | None) -> Decimal | None:
    """A limit as typed, as whole dollars, or None when empty.

    "12" and "12.00" are twelve dollars. Cents, letters, nothing at all, and
    amounts outside 1 to 999 are refused with a message that says why.
    """
    cleaned = (raw or "").strip().lstrip("$").strip()
    if not cleaned:
        return None
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"“{cleaned}” isn't an amount.") from None
    if amount != amount.to_integral_value():
        raise ValueError("Whole dollars, like 12.")
    if amount < 1:
        raise ValueError("A limit has to be at least $1.")
    if amount > MOST:
        raise ValueError("Three digits at most.")
    return amount.quantize(Decimal(1))


def default_limit(connection: sqlite3.Connection) -> Money | None:
    """The limit a new book starts with, or None for none."""
    value = _get(connection, DEFAULT_LIMIT)
    return Money(Decimal(value), CURRENCY) if value is not None else None


def set_default_limit(connection: sqlite3.Connection, raw: str | None) -> Money | None:
    """Set the default limit from what was typed, or clear it when empty."""
    amount = whole_dollars(raw)
    _put(connection, DEFAULT_LIMIT, str(amount) if amount is not None else None)
    return default_limit(connection)


def without_limit(connection: sqlite3.Connection) -> int:
    """How many books on the list have no limit."""
    return connection.execute(
        "SELECT COUNT(*) FROM entry WHERE ceiling IS NULL"
    ).fetchone()[0]


def fill(connection: sqlite3.Connection) -> int:
    """Give the default limit to every book that has none, and only those.

    Returns how many books it set. Nothing happens without a default.
    """
    limit = default_limit(connection)
    if limit is None:
        return 0
    cursor = connection.execute(
        "UPDATE entry SET ceiling = ?, ceiling_currency = ? WHERE ceiling IS NULL",
        (str(limit.amount), limit.currency),
    )
    connection.commit()
    return cursor.rowcount


def _get(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM setting WHERE name = ?", (name,)
    ).fetchone()
    return row["value"] if row else None


def _put(connection: sqlite3.Connection, name: str, value: str | None) -> None:
    if value is None:
        connection.execute("DELETE FROM setting WHERE name = ?", (name,))
    else:
        connection.execute(
            "INSERT INTO setting (name, value) VALUES (?, ?) "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
            (name, value),
        )
    connection.commit()


def ship_to_zip(connection: sqlite3.Connection) -> str | None:
    """The ZIP eBay prices calculated shipping to (S84, #182), or None."""
    return _get(connection, SHIP_TO)


def set_ship_to_zip(connection: sqlite3.Connection, raw: str | None) -> str | None:
    """Set the ZIP from what was typed, or clear it when empty.

    Refused unless it is five digits. The message never repeats what was
    typed: it is close to where somebody lives.
    """
    cleaned = (raw or "").strip()
    if cleaned and not _ZIP.fullmatch(cleaned):
        raise ValueError("A ZIP is five digits.")
    _put(connection, SHIP_TO, cleaned or None)
    return ship_to_zip(connection)


def stored_ship_to_zip() -> str | None:
    """The ZIP from the configured database, read fresh, for a search about
    to run. Opened here so every search, the CLI's on the Fly machine
    included, reads the one value Settings wrote."""
    from book_watch import db
    from book_watch.config import load_database_path

    with closing(db.connect(load_database_path())) as connection:
        db.migrate(connection)
        return ship_to_zip(connection)

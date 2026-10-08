"""The app's own settings (S83, #72).

One so far: the default limit, the whole-dollar amount each new book starts
with. It is a starting value, not inherited. A book copies it when added and
owns its limit from then on, so changing the default changes no book already
on the list. The books that have no limit can be given it on purpose, with
`fill`.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal, InvalidOperation

from book_watch.ebay.search import Money

#: Limits are in the one currency the app searches in.
CURRENCY = "USD"

#: Three digits at most: no book on the list is worth $1,000 to its reader.
MOST = 999

DEFAULT_LIMIT = "default_limit"


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
    row = connection.execute(
        "SELECT value FROM setting WHERE name = ?", (DEFAULT_LIMIT,)
    ).fetchone()
    return Money(Decimal(row["value"]), CURRENCY) if row else None


def set_default_limit(connection: sqlite3.Connection, raw: str | None) -> Money | None:
    """Set the default limit from what was typed, or clear it when empty."""
    amount = whole_dollars(raw)
    if amount is None:
        connection.execute("DELETE FROM setting WHERE name = ?", (DEFAULT_LIMIT,))
    else:
        connection.execute(
            "INSERT INTO setting (name, value) VALUES (?, ?) "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
            (DEFAULT_LIMIT, str(amount)),
        )
    connection.commit()
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

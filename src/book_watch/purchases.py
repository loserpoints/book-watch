"""What I bought, and the copy I last opened (S71, #223).

Marking a book bought writes a purchase and takes the entry off the list the
way removing does. Everything that stops for a removed book, the daily
check, Check all and the morning email, then stops for a bought one, with
nothing new to learn about a "bought" state that every query would have to
skip.

The copy last opened is remembered on the entry, so the bought sheet can
offer that copy's marketplace and price as a suggestion. It goes with the
entry, which is all it is for.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from book_watch import copies
from book_watch.ebay.search import Money
from book_watch.marketplaces import Marketplace
from book_watch.wantlist import Entry, get, moment

MARKETPLACES: tuple[Marketplace, ...] = ("ebay", "abebooks")


@dataclass(frozen=True, slots=True)
class Purchase:
    """One book bought, with what it needs to be shown after its entry went."""

    id: int
    title: str
    author: str | None
    cover_id: int | None
    paid: Money
    #: 'ebay' or 'abebooks', or None with `shop` naming anywhere else.
    marketplace: Marketplace | None
    shop: str | None
    bought_on: date
    #: The book's limit when it was bought, or None.
    limit: Money | None

    @property
    def verdict(self) -> str | None:
        """Paid at or under the limit it had, over it, or None with no limit
        in the same currency to judge by."""
        if self.limit is None or self.limit.currency != self.paid.currency:
            return None
        return "under" if self.paid.amount <= self.limit.amount else "over"


@dataclass(frozen=True, slots=True)
class Suggestion:
    """What the bought sheet offers, from the copy last opened."""

    marketplace: Marketplace
    #: Its delivered price, or None when its shipping isn't known.
    paid: Money | None
    opened_at: datetime


def opened(
    connection: sqlite3.Connection,
    entry_id: int,
    marketplace: str,
    item_id: str,
    now: datetime,
) -> None:
    """Remember the copy of this book just opened. Anything not a known
    marketplace, or an empty id, is ignored: this is only ever a hint."""
    if marketplace not in MARKETPLACES or not item_id:
        return
    connection.execute(
        "UPDATE entry SET opened_marketplace = ?, opened_item_id = ?, opened_at = ? "
        "WHERE id = ?",
        (
            marketplace,
            item_id,
            now.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            entry_id,
        ),
    )


def suggestion(connection: sqlite3.Connection, entry: Entry) -> Suggestion | None:
    """The copy of this book last opened from the app, as a suggestion, or
    None when none was. A copy no longer stored still names its marketplace."""
    row = connection.execute(
        "SELECT opened_marketplace, opened_item_id, opened_at FROM entry WHERE id = ?",
        (entry.id,),
    ).fetchone()
    if row is None or row["opened_marketplace"] is None:
        return None
    at = moment(row["opened_at"])
    if at is None:
        return None
    key = (row["opened_marketplace"], row["opened_item_id"])
    paid = None
    for scope in ("us", "everywhere"):
        found = next(
            (
                c
                for c in copies.for_entry(connection, entry, scope=scope)
                if c.key == key
            ),
            None,
        )
        if found is not None:
            paid = found.landed_cost
            break
    return Suggestion(marketplace=row["opened_marketplace"], paid=paid, opened_at=at)


class Refused(ValueError):
    """What was entered can't be recorded, with what to say about it."""


def amount(raw: str) -> Decimal:
    """A price as typed: "7.80", "$7.80" or "7". Refused when it isn't one."""
    cleaned = raw.strip().lstrip("$").strip()
    if not cleaned:
        raise Refused("Say what you paid.")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        raise Refused(f"“{raw.strip()}” isn't an amount.") from None
    if not parsed.is_finite() or parsed <= 0:
        raise Refused("What you paid has to be more than nothing.")
    return parsed.quantize(Decimal("0.01"))


def buy(
    connection: sqlite3.Connection,
    entry_id: int,
    *,
    paid: Decimal,
    currency: str,
    marketplace: Marketplace | None,
    shop: str | None,
    bought_on: date,
) -> Purchase | None:
    """Record the purchase and take the book off the list, together.

    Returns None when the entry has already gone: removed, or bought from
    another tab, and the list is then already right.
    """
    if (marketplace is None) == (not shop):
        raise ValueError("A purchase names a marketplace or a shop, not both.")
    try:
        entry = get(connection, entry_id)
    except LookupError:
        return None
    limit = entry.will_pay
    connection.execute("BEGIN")
    try:
        purchase_id = connection.execute(
            """
            INSERT INTO purchase (
                work_id, title, author, cover_id, paid, currency,
                marketplace, shop, bought_on, ceiling, ceiling_currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                entry.work_id,
                entry.name,
                entry.author,
                entry.cover,
                str(paid),
                currency,
                marketplace,
                shop or None,
                bought_on.isoformat(),
                str(limit.amount) if limit else None,
                limit.currency if limit else None,
            ),
        ).fetchone()["id"]
        connection.execute("DELETE FROM entry WHERE id = ?", (entry_id,))
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    return everything(connection, only=purchase_id)[0]


def everything(
    connection: sqlite3.Connection, *, only: int | None = None
) -> list[Purchase]:
    """Every purchase, most recently bought first."""
    rows = connection.execute(
        "SELECT * FROM purchase"
        + (" WHERE id = ?" if only is not None else "")
        + " ORDER BY bought_on DESC, id DESC",
        (only,) if only is not None else (),
    )
    return [_to_purchase(row) for row in rows]


def total(purchases: list[Purchase]) -> Money | None:
    """What they cost together, or None when they were paid in more than one
    currency and adding them would mean nothing."""
    if not purchases:
        return None
    currencies = {p.paid.currency for p in purchases}
    if len(currencies) != 1:
        return None
    return Money(sum((p.paid.amount for p in purchases), Decimal(0)), currencies.pop())


def _to_purchase(row: sqlite3.Row) -> Purchase:
    limit = (
        Money(Decimal(row["ceiling"]), row["ceiling_currency"])
        if row["ceiling"] is not None
        else None
    )
    return Purchase(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        cover_id=row["cover_id"],
        paid=Money(Decimal(row["paid"]), row["currency"]),
        marketplace=row["marketplace"],
        shop=row["shop"],
        bought_on=date.fromisoformat(row["bought_on"]),
        limit=limit,
    )

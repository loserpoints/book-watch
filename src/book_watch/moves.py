"""Which way the latest check moved a price (S72, #164).

The want list follows one price per book, its "from" price, and says whether
the latest check moved it. So each check notes that price just before it
stores anything, and the list compares the price now with the note. The next
check that leaves the price where it was takes a note equal to it, and the
caret goes.

A check stores more than once: eBay's search, then AbeBooks' page, read for
US sellers and everywhere. The note is taken by the first of them, inside
`sweeps.store`, so every path a check can start from takes it, and the others
within `SAME_CHECK` leave it alone. Copies examined after the search still
count toward the same check, since they move the price now and not the note.

A copy on a book's page carries its own caret, read from its price history:
whether the latest check that saw it changed its delivered price.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from book_watch import standing, wantlist
from book_watch.ebay.search import Money
from book_watch.wantlist import Entry, moment

#: Stores this close together are one check: eBay's and AbeBooks', for US
#: sellers and everywhere, which follow each other within seconds.
SAME_CHECK = timedelta(minutes=10)

Direction = Literal["down", "up"]


@dataclass(frozen=True, slots=True)
class Move:
    """Which way a price went, and what it was before."""

    direction: Direction
    was: Money


def before_check(connection: sqlite3.Connection, work_id: int, now: datetime) -> None:
    """Note each entry's "from" price as it stands, unless this check already
    did. Called by `sweeps.store` before it writes anything."""
    rows = connection.execute(
        "SELECT id, checked_from_at FROM entry WHERE work_id = ?", (work_id,)
    ).fetchall()
    for row in rows:
        noted = moment(row["checked_from_at"])
        if noted is not None and now - noted < SAME_CHECK:
            continue
        entry = wantlist.get(connection, row["id"])
        lead = standing.glance(connection, entry).headline
        price = lead.cheapest if lead else None
        connection.execute(
            "UPDATE entry SET checked_from = ?, checked_from_currency = ?, "
            "checked_from_at = ? WHERE id = ?",
            (
                str(price.amount) if price else None,
                price.currency if price else None,
                now.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                row["id"],
            ),
        )


def of_from(entry: Entry, now: Money | None) -> Move | None:
    """How the latest check moved this book's "from" price, or None when it
    didn't, or there's no price before or now to compare."""
    was = entry.from_before_check
    return _between(was, now)


def _between(was: Money | None, now: Money | None) -> Move | None:
    if was is None or now is None or was.currency != now.currency:
        return None
    if now.amount == was.amount:
        return None
    return Move("down" if now.amount < was.amount else "up", was)


def of_copies(
    connection: sqlite3.Connection, work_id: int
) -> dict[tuple[str, str], Move]:
    """Each copy of this book whose delivered price the latest check that saw
    it changed, by its marketplace and id.

    A sighting is written only when a copy's price changes or it comes back,
    so a copy moved at its latest check when its newest sighting belongs to
    that check and differs from the one before. A price whose shipping isn't
    known can't be compared and gets no caret.
    """
    latest = {
        row["marketplace"]: moment(row["at"])
        for row in connection.execute(
            "SELECT marketplace, max(at) AS at FROM sweep WHERE work_id = ? "
            "GROUP BY marketplace",
            (work_id,),
        )
    }
    rows = connection.execute(
        """
        SELECT sighting.marketplace, sighting.item_id, sighting.price,
               sighting.currency, sighting.shipping, sweep.at
          FROM sighting JOIN sweep ON sweep.id = sighting.sweep_id
         WHERE sighting.work_id = ?
         ORDER BY sighting.marketplace, sighting.item_id, sighting.sweep_id DESC
        """,
        (work_id,),
    )
    moves: dict[tuple[str, str], Move] = {}
    newest: dict[tuple[str, str], sqlite3.Row] = {}
    done: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["marketplace"], row["item_id"])
        if key in done:
            continue
        if key not in newest:
            newest[key] = row
            continue
        done.add(key)
        last = newest[key]
        checked = latest.get(row["marketplace"])
        at = moment(last["at"])
        if checked is None or at is None or checked - at >= SAME_CHECK:
            continue
        move = _between(_delivered(row), _delivered(last))
        if move is not None:
            moves[key] = move
    return moves


def _delivered(row: sqlite3.Row) -> Money | None:
    if row["shipping"] is None:
        return None
    return Money(Decimal(row["price"]) + Decimal(row["shipping"]), row["currency"])

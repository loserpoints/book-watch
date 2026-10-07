"""How often copies' prices move, counted from the price history (S72, #164).

    python -m book_watch.price_moves [days]

Before S72 shows a copy's price going up or down, this says how often that
happens on the books on the list: how many copies moved in the last `days`
(14 by default), which way, by how much, and how many crossed their book's
limit. It reads the database and asks no service anything.

Prints counts only. The workflow that runs it has public logs, and titles,
sellers and prices are Alan's, not the public's.
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from book_watch import db
from book_watch.config import load_database_path

#: The sizes a move is counted in, in dollars: a few cents is shipping noise,
#: a few dollars is a seller repricing.
SIZES = (Decimal("0.50"), Decimal("2"))


@dataclass
class Moves:
    """What the price history says moved, and how."""

    days: int
    books: int = 0
    copies: int = 0
    down: Counter = field(default_factory=Counter)
    up: Counter = field(default_factory=Counter)
    #: Moves that crossed the book's limit, each way.
    under: int = 0
    over: int = 0
    #: Copies that moved, and books with at least one that did.
    copies_moved: int = 0
    books_moved: int = 0
    #: Moves that can't be judged: shipping unknown, or a currency change.
    unknown: int = 0

    def lines(self) -> list[str]:
        def sized(counts: Counter) -> str:
            return ", ".join(f"{counts[label]} {label}" for label in _labels())

        return [
            f"In the last {self.days} days, on {self.books} books with "
            f"{self.copies} copies in the price history:",
            f"Down {sum(self.down.values())}: {sized(self.down)}",
            f"Up {sum(self.up.values())}: {sized(self.up)}",
            f"Went under the limit: {self.under}. Went over it: {self.over}.",
            f"Copies that moved: {self.copies_moved}. "
            f"Books with a copy that moved: {self.books_moved}.",
            f"Not counted, shipping or currency unknown: {self.unknown}.",
        ]


def _labels() -> list[str]:
    small, large = SIZES
    return [f"under ${small}", f"${small} to ${large}", f"over ${large}"]


def _size(change: Decimal) -> str:
    small, large = SIZES
    labels = _labels()
    if change < small:
        return labels[0]
    return labels[1] if change <= large else labels[2]


def _delivered(row: sqlite3.Row) -> tuple[Decimal, str] | None:
    if row["shipping"] is None:
        return None
    return Decimal(row["price"]) + Decimal(row["shipping"]), row["currency"]


def count(connection: sqlite3.Connection, now: datetime, days: int = 14) -> Moves:
    """Every change between one sighting of a copy and the next, where the
    later one falls in the window. Books no longer on the list are left out.

    A sighting is written only when a copy's price changes or it comes back
    after being away, so consecutive sightings at the same price are a
    return, not a move, and aren't counted.
    """
    since = (now - timedelta(days=days)).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    limits = {
        row["work_id"]: (Decimal(row["ceiling"]), row["ceiling_currency"])
        for row in connection.execute(
            "SELECT work_id, ceiling, ceiling_currency FROM entry "
            "WHERE ceiling IS NOT NULL"
        )
    }
    moves = Moves(days=days)
    moves.books = connection.execute(
        "SELECT count(DISTINCT work_id) FROM entry"
    ).fetchone()[0]
    rows = connection.execute(
        """
        SELECT sighting.marketplace, sighting.item_id, sighting.work_id,
               sighting.price, sighting.currency, sighting.shipping, sweep.at
          FROM sighting
          JOIN sweep ON sweep.id = sighting.sweep_id
         WHERE sighting.work_id IN (SELECT work_id FROM entry)
         ORDER BY sighting.marketplace, sighting.item_id, sighting.work_id,
                  sighting.sweep_id
        """
    )
    last_key, last_row = None, None
    copies, moved, books_moved = set(), set(), set()
    for row in rows:
        key = (row["marketplace"], row["item_id"], row["work_id"])
        copies.add(key)
        previous = last_row if key == last_key else None
        last_key, last_row = key, row
        if previous is None or row["at"] < since:
            continue
        was, now_ = _delivered(previous), _delivered(row)
        if was is None or now_ is None or was[1] != now_[1]:
            if previous["price"] != row["price"]:
                moves.unknown += 1
            continue
        change = now_[0] - was[0]
        if change == 0:
            continue
        (moves.down if change < 0 else moves.up)[_size(abs(change))] += 1
        moved.add(key)
        books_moved.add(row["work_id"])
        limit = limits.get(row["work_id"])
        if limit is not None and limit[1] == now_[1]:
            if was[0] > limit[0] >= now_[0]:
                moves.under += 1
            elif was[0] <= limit[0] < now_[0]:
                moves.over += 1
    moves.copies = len(copies)
    moves.copies_moved = len(moved)
    moves.books_moved = len(books_moved)
    return moves


def main(argv: list[str]) -> int:
    if len(argv) > 1 or (argv and not argv[0].isdigit()):
        print("Usage: python -m book_watch.price_moves [days]")
        return 2
    days = int(argv[0]) if argv else 14
    with closing(db.connect(load_database_path())) as connection:
        for line in count(connection, datetime.now(UTC), days).lines():
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

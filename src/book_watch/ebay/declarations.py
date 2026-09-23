"""The record of what sellers declared, so eBay is asked once per listing.

`Declarations` is what the rest of the app talks to. It answers the same
question `ItemDetailClient.declared_by` does, but reads what we already know
first and writes down whatever it learns.

One request per item, ever. Decision 33: the per-listing detail call is
affordable only on that basis — a fifty-result search is fifty calls against a
5,000-a-day allowance, and a version of this that re-asked on every page view
would spend the day's budget on one book.
"""

from __future__ import annotations

import sqlite3

from book_watch.ebay.detail import Declared, ItemDetailClient

_COLUMNS = "item_id, isbn, format, publisher, published, category"


class Declarations:
    """What sellers said, asked for once and kept."""

    def __init__(
        self, connection: sqlite3.Connection, client: ItemDetailClient
    ) -> None:
        self._connection = connection
        self._client = client

    def of(self, item_id: str) -> Declared:
        """What this listing declares, asking eBay only if we have never asked.

        A listing that has ended comes back with nothing in it, and that is
        recorded like any other answer. It was asked about; asking again would
        get the same nothing.
        """
        row = self._connection.execute(
            f"SELECT {_COLUMNS} FROM listing_declaration WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if row is not None:
            return _to_declared(row)

        declared = self._client.declared_by(item_id)
        self._remember(declared)
        return declared

    def known(self, item_id: str) -> bool:
        """Whether this listing can be answered for without asking eBay."""
        row = self._connection.execute(
            "SELECT 1 FROM listing_declaration WHERE item_id = ?", (item_id,)
        ).fetchone()
        return row is not None

    def unasked(self, item_ids: list[str]) -> list[str]:
        """Which of these have never been asked about, in the order given.

        For a caller that wants to know what a page will cost before spending
        it — or that has a budget and needs to stop partway.
        """
        if not item_ids:
            return []
        placeholders = ",".join("?" * len(item_ids))
        rows = self._connection.execute(
            "SELECT item_id FROM listing_declaration "
            f"WHERE item_id IN ({placeholders})",
            item_ids,
        )
        seen = {row["item_id"] for row in rows}
        return [item_id for item_id in item_ids if item_id not in seen]

    def _remember(self, declared: Declared) -> None:
        self._connection.execute(
            f"""
            INSERT INTO listing_declaration ({_COLUMNS})
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (item_id) DO NOTHING
            """,
            (
                declared.item_id,
                declared.isbn,
                declared.format,
                declared.publisher,
                declared.published,
                declared.category,
            ),
        )


def _to_declared(row: sqlite3.Row) -> Declared:
    return Declared(
        item_id=row["item_id"],
        isbn=row["isbn"],
        format=row["format"],
        publisher=row["publisher"],
        published=row["published"],
        category=row["category"],
    )

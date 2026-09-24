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

_COLUMNS = "item_id, isbn, author, format, publisher, published, category"

#: Which fields the code above reads out of an eBay listing.
#:
#: **Bump this whenever that changes.** A row stamped below it was captured by
#: code that did not look at everything this code looks at, so it may be
#: missing an answer eBay would have given. Forgetting to bump is the failure
#: mode, and it is not hypothetical: the rule that reads the declared author
#: shipped against rows captured before there was an author column, was null
#: on every one of them, and was dead in production while passing every test.
#:
#: A change in what is *done* with these fields counts too. Reading the same
#: column more carefully is still a change in what was captured.
#:
#: 1: isbn, author, format, publisher, published, category.
CAPTURE = 1


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

    def outdated(self, item_ids: list[str]) -> list[str]:
        """Which of these were captured by code that read less than this one.

        Stale, not absent: every one of these still answers `of()` with what
        it has. This is the queue for improving them, not a list of gaps.
        """
        if not item_ids:
            return []
        placeholders = ",".join("?" * len(item_ids))
        rows = self._connection.execute(
            "SELECT item_id FROM listing_declaration "
            f"WHERE item_id IN ({placeholders}) AND captured_by < ?",
            [*item_ids, CAPTURE],
        )
        behind = {row["item_id"] for row in rows}
        return [item_id for item_id in item_ids if item_id in behind]

    def refresh(self, item_id: str) -> Declared:
        """Ask eBay again about a listing we already have an older answer for.

        A live seller's current declaration replaces what we stored, field for
        field, including a field they have cleared — they are the authority on
        their own listing and an edit is a fact about it.

        A listing eBay no longer has is the opposite case. Its emptiness says
        nothing about the book, so everything stored survives and only the
        stamp moves: we asked, at this version, and there is nothing further
        to learn. Copies are kept for ever now, so this is the common case
        rather than an edge one.
        """
        declared = self._client.declared_by(item_id)
        if not declared.present:
            self._connection.execute(
                "UPDATE listing_declaration SET captured_by = ? WHERE item_id = ?",
                (CAPTURE, item_id),
            )
            return self.of(item_id)
        self._write(declared, replace=True)
        return declared

    def _remember(self, declared: Declared) -> None:
        self._write(declared, replace=False)

    def _write(self, declared: Declared, *, replace: bool) -> None:
        resolution = (
            """
            DO UPDATE SET
                isbn = excluded.isbn,
                author = excluded.author,
                format = excluded.format,
                publisher = excluded.publisher,
                published = excluded.published,
                category = excluded.category,
                captured_by = excluded.captured_by
            """
            if replace
            else "DO NOTHING"
        )
        self._connection.execute(
            f"""
            INSERT INTO listing_declaration ({_COLUMNS}, captured_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (item_id) {resolution}
            """,
            (
                declared.item_id,
                declared.isbn,
                declared.author,
                declared.format,
                declared.publisher,
                declared.published,
                declared.category,
                CAPTURE,
            ),
        )


def _to_declared(row: sqlite3.Row) -> Declared:
    return Declared(
        item_id=row["item_id"],
        isbn=row["isbn"],
        author=row["author"],
        format=row["format"],
        publisher=row["publisher"],
        published=row["published"],
        category=row["category"],
    )

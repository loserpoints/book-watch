"""Copies offered for sale, stored and graded.

A *copy* is one object in one seller's hands at one price. A work has many
editions and an edition has many copies, which is why this is not called
"listing": the word has to survive a second marketplace, and "copy" is what a
person is actually buying.

The page reads this and nothing else. That is measured rather than preferred:
one eBay search takes about 1.8 seconds and one per-listing detail call about
0.51, so a page that fetched details for its own fifty results would take
twenty-five seconds. Everything shown here was written down earlier.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from book_watch.ebay.search import Listing, Money
from book_watch.matching import Evidence, Target, Tier, grade
from book_watch.wantlist import Entry

#: Everything the grader needs about one copy, in one query rather than three
#: lookups per row. The joins are left joins throughout: a copy nobody has
#: asked eBay about, and a number nobody has asked Open Library about, are
#: both ordinary states rather than missing data.
_SELECT = """
SELECT copy.item_id,
       copy.title,
       copy.url,
       copy.price,
       copy.currency,
       copy.shipping,
       copy.condition,
       copy.seller,
       copy.thumbnail,
       copy.epid,
       copy.seen_at,
       declaration.item_id AS asked_ebay,
       declaration.isbn    AS declared_isbn,
       declaration.author  AS declared_author,
       declaration.format  AS declared_format,
       declaration.publisher AS declared_publisher,
       declaration.published AS declared_year,
       declaration.category  AS category,
       identity.title      AS identity_title
  FROM copy
  LEFT JOIN listing_declaration AS declaration
         ON declaration.item_id = copy.item_id
  LEFT JOIN openlibrary_edition AS identity
         ON identity.isbn = declaration.isbn AND identity.found = 1
 WHERE copy.work_id = ?
"""


@dataclass(frozen=True, slots=True)
class Copy:
    """One copy for sale, with how sure we are that it is the book."""

    item_id: str
    title: str
    url: str
    price: Money
    shipping: Money | None
    tier: Tier
    condition: str | None = None
    seller: str | None = None
    thumbnail: str | None = None
    category: str | None = None
    declared_author: str | None = None
    declared_format: str | None = None
    declared_publisher: str | None = None
    declared_year: str | None = None
    #: Whether eBay has been asked what this seller declared. False means the
    #: copy is graded on its listing name alone and may firm up later.
    looked_at: bool = True

    @property
    def landed_cost(self) -> Money | None:
        """Price plus shipping, or `None` when that cannot be known.

        Same rule as the search client: shipping that was never stated, or
        stated in another currency, gives no total rather than a wrong one.
        """
        if self.shipping is None or self.shipping.currency != self.price.currency:
            return None
        return Money(self.price.amount + self.shipping.amount, self.price.currency)

    @property
    def sort_key(self) -> Decimal:
        """Cheapest first, with an unknown total ranking as its price alone.

        A copy whose shipping eBay declined to state is not free and not
        infinite. Ranking it by its price is the least wrong of the available
        lies, and the page says which it is.
        """
        landed = self.landed_cost
        return landed.amount if landed else self.price.amount


def store(
    connection: sqlite3.Connection, work_id: int, listings: list[Listing]
) -> None:
    """Replace what is on sale for this book with what was just found.

    Replace rather than merge: a copy that has stopped appearing has been
    sold or withdrawn, and keeping it would turn this table into a list of
    things that used to be buyable.
    """
    connection.execute("DELETE FROM copy WHERE work_id = ?", (work_id,))
    connection.executemany(
        """
        INSERT INTO copy (
            item_id, work_id, title, url, price, currency, shipping,
            condition, seller, thumbnail, epid, listed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                listing.item_id,
                work_id,
                listing.title,
                listing.item_web_url,
                str(listing.price.amount),
                listing.price.currency,
                _shipping_of(listing),
                listing.condition,
                listing.seller,
                listing.thumbnail_url,
                listing.epid,
                listing.listing_date.isoformat() if listing.listing_date else None,
            )
            for listing in listings
        ],
    )
    # New copies are new work, so the book stops counting as enriched. That is
    # what schedules the next pass, and what makes the want-list say so again.
    connection.execute(
        "UPDATE work SET copies_fetched_at = datetime('now'), enriched_at = NULL "
        "WHERE id = ?",
        (work_id,),
    )


def for_entry(connection: sqlite3.Connection, entry: Entry) -> list[Copy]:
    """Every stored copy for this book, graded and cheapest first within a tier.

    Sorting happens **inside** a tier and never across one. A reader sees one
    group today, so this looks like an ordering with an extra step — decision
    33 measured that on the other hunt the cheapest certain copy was wrong,
    and a sort that crossed tiers would have to be unpicked to support it.
    """
    target = _target(connection, entry)
    copies = [
        _to_copy(row, target, entry)
        for row in connection.execute(_SELECT, (entry.work_id,))
    ]
    order = {"certain": 0, "probable": 1, "possible": 2, "excluded": 3}
    copies.sort(key=lambda copy: (order[copy.tier], copy.sort_key))
    return copies


def unasked(copies: list[Copy]) -> list[str]:
    """Item ids nobody has asked eBay about, so a caller can go and find out."""
    return [copy.item_id for copy in copies if not copy.looked_at]


def _target(connection: sqlite3.Connection, entry: Entry) -> Target:
    isbns = {
        row["isbn"]
        for row in connection.execute(
            "SELECT isbn FROM edition WHERE work_id = ? AND isbn IS NOT NULL",
            (entry.work_id,),
        )
    }
    epids = {
        row["epid"]
        for row in connection.execute(
            "SELECT DISTINCT epid FROM copy "
            "WHERE work_id = ? AND epid IS NOT NULL AND item_id IN ("
            "  SELECT item_id FROM listing_declaration WHERE isbn IN ("
            "    SELECT isbn FROM edition WHERE work_id = ? AND isbn IS NOT NULL))",
            (entry.work_id, entry.work_id),
        )
    }
    return Target(
        title=entry.title or entry.search_query,
        # Only ever used to reject. An entry added before authors were asked
        # for has none, and then nothing is rejected on this basis.
        author=entry.author,
        isbns=frozenset(isbns),
        epids=frozenset(epids),
    )


def _to_copy(row: sqlite3.Row, target: Target, entry: Entry) -> Copy:
    evidence = Evidence(
        listing_title=row["title"],
        epid=row["epid"],
        declared_isbn=row["declared_isbn"],
        identity=row["identity_title"],
        declared_author=row["declared_author"],
    )
    return Copy(
        item_id=row["item_id"],
        title=row["title"],
        url=row["url"],
        price=Money(_amount(row["price"]), row["currency"]),
        shipping=Money(_amount(row["shipping"]), row["currency"])
        if row["shipping"] is not None
        else None,
        tier=grade(evidence, target, hunt=entry.hunt),
        condition=row["condition"],
        seller=row["seller"],
        thumbnail=row["thumbnail"],
        category=row["category"],
        declared_author=row["declared_author"],
        declared_format=row["declared_format"],
        declared_publisher=row["declared_publisher"],
        declared_year=row["declared_year"],
        looked_at=row["asked_ebay"] is not None,
    )


def _shipping_of(listing: Listing) -> str | None:
    cost = listing.shipping_cost
    if cost is None or cost.currency != listing.price.currency:
        return None
    return str(cost.amount)


def _amount(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError):
        # A hand-edited row should not take the page down.
        return Decimal(0)

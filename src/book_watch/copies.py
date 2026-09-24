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
from book_watch.isbn import normalise
from book_watch.matching import Evidence, Target, Tier, grade, is_this_book
from book_watch.wantlist import Entry

#: Everything the grader needs about one copy, in one query rather than three
#: lookups per row. The joins are left joins throughout: a copy nobody has
#: asked eBay about, and a number nobody has asked Open Library about, are
#: both ordinary states rather than missing data.
#:
#: Restricted to the newest sweep, because copies are kept now rather than
#: deleted and the page's question is still "what is buyable today". The
#: comparison is on a sweep id rather than a time: two sweeps a second apart
#: are different sweeps and a timestamp cannot say so. `IS` rather than `=`
#: so that a book with no sweep at all matches its copies instead of
#: silently showing none.
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
   AND copy.last_sweep_id IS (
       SELECT sweep.id FROM sweep WHERE sweep.work_id = ?
     ORDER BY sweep.id DESC LIMIT 1
   )
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


def store(connection: sqlite3.Connection, work_id: int, listings: list[Listing]) -> int:
    """Record what eBay just returned, keeping everything seen before it.

    This used to delete the book's copies and reinsert the new ones, which
    answered the page's question — what is for sale now — by destroying the
    answer to a later one. What a copy has cost over time is the cheapest
    evidence we will ever have for judging a price, and it costs no requests
    to keep, because it arrives in a search we already ran.

    So a sweep now *adds*: a sweep row, an upsert per copy, and a sighting for
    any copy whose price moved or that has come back after being absent. A
    copy that stopped appearing is left where it is, pointing at the last
    sweep that saw it. Returns the sweep id.
    """
    sweep_id = connection.execute(
        "INSERT INTO sweep (work_id) VALUES (?) RETURNING id", (work_id,)
    ).fetchone()["id"]

    previous = {
        row["item_id"]: row
        for row in connection.execute(
            "SELECT item_id, price, currency, shipping, condition, last_sweep_id "
            "FROM copy WHERE work_id = ?",
            (work_id,),
        )
    }
    latest_before = connection.execute(
        "SELECT id FROM sweep WHERE work_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
        (work_id, sweep_id),
    ).fetchone()
    was_current = latest_before["id"] if latest_before else None

    fresh: list[str] = []
    for listing in listings:
        shipping = _shipping_of(listing)
        before = previous.get(listing.item_id)
        if before is None:
            fresh.append(listing.item_id)
        connection.execute(
            """
            INSERT INTO copy (
                item_id, work_id, title, url, price, currency, shipping,
                condition, seller, thumbnail, epid, listed_at,
                first_seen_at, last_seen_at, last_sweep_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      datetime('now'), datetime('now'), ?)
            ON CONFLICT (item_id, work_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                price = excluded.price,
                currency = excluded.currency,
                shipping = excluded.shipping,
                condition = excluded.condition,
                seller = excluded.seller,
                thumbnail = excluded.thumbnail,
                epid = excluded.epid,
                listed_at = excluded.listed_at,
                last_seen_at = datetime('now'),
                last_sweep_id = excluded.last_sweep_id
            """,
            (
                listing.item_id,
                work_id,
                listing.title,
                listing.item_web_url,
                str(listing.price.amount),
                listing.price.currency,
                shipping,
                listing.condition,
                listing.seller,
                listing.thumbnail_url,
                listing.epid,
                listing.listing_date.isoformat() if listing.listing_date else None,
                sweep_id,
            ),
        )
        if _worth_recording(before, listing, shipping, was_current):
            connection.execute(
                "INSERT INTO sighting "
                "(item_id, work_id, sweep_id, price, currency, shipping, condition) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    listing.item_id,
                    work_id,
                    sweep_id,
                    str(listing.price.amount),
                    listing.price.currency,
                    shipping,
                    listing.condition,
                ),
            )

    # Only genuinely new copies are new work. This used to clear
    # unconditionally, so every refresh scheduled a full enrichment pass and
    # spent Open Library requests re-asking about numbers already answered —
    # which is the traffic we have the least room to waste.
    if fresh:
        connection.execute(
            "UPDATE work SET copies_fetched_at = datetime('now'), enriched_at = NULL "
            "WHERE id = ?",
            (work_id,),
        )
    else:
        connection.execute(
            "UPDATE work SET copies_fetched_at = datetime('now') WHERE id = ?",
            (work_id,),
        )
    return sweep_id


def _worth_recording(
    before: sqlite3.Row | None,
    listing: Listing,
    shipping: str | None,
    was_current: int | None,
) -> bool:
    """Is this sighting something the last one does not already say?

    Only changes are written, which is the whole reason the history stays
    small: an unchanged price recorded every sweep is one fact repeated daily
    forever. A row means "this is the price from this sweep onward", and holds
    until the next row.

    A copy we have never seen is always worth recording — its first sighting
    is a change from nothing. So is one that has come back after being absent,
    even at the identical price: without that row, a gap reads as one
    continuous offer, and that is a claim we cannot support.
    """
    if before is None:
        return True
    if before["last_sweep_id"] != was_current:
        return True  # it was not in the previous sweep — a reappearance
    return (
        before["price"] != str(listing.price.amount)
        or before["currency"] != listing.price.currency
        or before["shipping"] != shipping
        or before["condition"] != listing.condition
    )


def price_history(
    connection: sqlite3.Connection, work_id: int, item_id: str
) -> list[tuple[str, Money, Money | None]]:
    """What one copy has cost, each time that changed, oldest first.

    Returned as (when, price, shipping). Only changes are stored, so a reading
    holds from its sweep until the next one — two entries a month apart mean
    the price was unchanged between them, not that nobody looked.
    """
    return [
        (
            row["at"],
            Money(Decimal(row["price"]), row["currency"]),
            Money(Decimal(row["shipping"]), row["currency"])
            if row["shipping"] is not None
            else None,
        )
        for row in connection.execute(
            "SELECT sweep.at, sighting.price, sighting.currency, sighting.shipping "
            "FROM sighting JOIN sweep ON sweep.id = sighting.sweep_id "
            "WHERE sighting.work_id = ? AND sighting.item_id = ? "
            "ORDER BY sighting.sweep_id",
            (work_id, item_id),
        )
    ]


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
        for row in connection.execute(_SELECT, (entry.work_id, entry.work_id))
    ]
    order = {"certain": 0, "probable": 1, "possible": 2, "excluded": 3}
    copies.sort(key=lambda copy: (order[copy.tier], copy.sort_key))
    return copies


def unasked(copies: list[Copy]) -> list[str]:
    """Item ids nobody has asked eBay about, so a caller can go and find out."""
    return [copy.item_id for copy in copies if not copy.looked_at]


#: Every number declared on this book's copies, with what the catalogue calls
#: it and who a seller said wrote it. All three are observations already paid
#: for, which is why deriving costs no requests.
_DECLARED_NUMBERS = """
SELECT DISTINCT declaration.isbn,
                declaration.author AS declared_author,
                identity.title     AS catalogue_title
  FROM copy
  JOIN listing_declaration AS declaration ON declaration.item_id = copy.item_id
  JOIN openlibrary_edition AS identity
       ON identity.isbn = declaration.isbn AND identity.found = 1
 WHERE copy.work_id = ? AND declaration.isbn IS NOT NULL
"""


#: Which product id each declared number was seen alongside, on this book's
#: copies. One query rather than one per product id, because a book with fifty
#: copies would otherwise cost fifty.
_DECLARED_PRODUCT_IDS = """
SELECT DISTINCT copy.epid, declaration.isbn
  FROM copy
  JOIN listing_declaration AS declaration ON declaration.item_id = copy.item_id
 WHERE copy.work_id = ? AND copy.epid IS NOT NULL AND declaration.isbn IS NOT NULL
"""


def _target(connection: sqlite3.Connection, entry: Entry) -> Target:
    """What we are looking for, worked out fresh every time.

    Which numbers count as this book is **derived, not stored**. It used to be
    a table a pass wrote conclusions into, and a conclusion stored under one
    set of rules survives the rules changing — which is how a different book
    called *Breaking and Entering* stayed matched behind the check written to
    reject it.

    Now it is a query over things we observed: what sellers declared, what the
    catalogue says those numbers are, who sellers say wrote them. Change the
    rule and every book on the list is re-judged on the next page view, for
    nothing.
    """
    typed = normalise(entry.typed) if entry.typed else None
    wanted = Target(
        title=entry.title or entry.search_query,
        # Only ever used to reject. An entry added before authors were asked
        # for has none, and then nothing is rejected on this basis.
        author=entry.author,
    )

    isbns = {
        row["isbn"]
        for row in connection.execute(_DECLARED_NUMBERS, (entry.work_id,))
        if is_this_book(row["catalogue_title"], row["declared_author"], wanted)
    }
    # What somebody typed is not a conclusion and is never re-judged.
    if typed:
        isbns.add(typed)

    # A product id counts when a copy carrying it declared one of the numbers
    # above. eBay's `epid` over-merges (decision 33), so it is only ever
    # reached this way — through a number — never asserted on its own.
    epids = {
        row["epid"]
        for row in connection.execute(_DECLARED_PRODUCT_IDS, (entry.work_id,))
        if row["isbn"] in isbns
    }
    return Target(
        title=wanted.title,
        author=wanted.author,
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

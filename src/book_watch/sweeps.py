"""What a search saw, and when it saw it.

A *sweep* is one search of one marketplace for one book in one scope, and
everything this module does is about recording one honestly: which copies it
returned, what they cost, whether it saw the whole market or only a window, and
how long its answer stays current.

Kept apart from `copies` because the questions differ in tense. That module
asks what is for sale now; this one asks what was true when we last looked,
and a page that confuses the two shows copies that sold days ago.

A sweep **adds**. It used to delete a book's copies and reinsert them, which
answered the page's question by destroying the answer to a later one — what a
copy has cost over time is the cheapest evidence we will ever have for judging
a price, and it arrives in a search we already ran.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from book_watch import counts, monitoring
from book_watch.ebay.search import Listing, Money, Scope
from book_watch.marketplaces import Marketplace, is_us

#: How long a book's results are treated as current.
#:
#: **The reason is not the API budget.** Ten books at the theoretical ceiling
#: of twenty-four sweeps each is 240 searches a day against an allowance of
#: 5,000, so cost does not constrain this at all.
#:
#: The reason is that results have to hold still long enough to act on. Look at
#: one book, go and check another, come back — if a sweep ran in between and
#: the list reordered, you can lose the copy you had already decided to buy.
#: Freshness that costs you the purchase is a bad trade, and the market does
#: not move in minutes: these listings sit for weeks.
#:
#: A secondary effect, worth knowing. Ungated, sweep frequency would track how
#: often somebody clicks, so the price history's time axis would be shaped by
#: one person's habits rather than by the market.
#:
#: One named place, so #72 can read it from somewhere else later without a
#: hunt.
CURRENT_FOR = timedelta(hours=1)


def due_for_sweep(
    connection: sqlite3.Connection,
    work_id: int,
    *,
    scope: Scope = "us",
    marketplace: Marketplace = "ebay",
    current_for: timedelta | None = None,
) -> bool:
    """Should opening this book spend a search?

    Yes when it has never been searched for, or when the last sweep is older
    than `current_for`. Asking to look again does not come through here — that
    is an explicit act and bypasses the gate, because a button that does
    nothing for fifty-nine minutes is worse than no button.

    The policy lives here rather than at the call site so there is one answer
    to the question. It is enforced at the call site because by the time
    `store` is reached the request has already been spent.

    `current_for` is read from the module rather than bound as a default
    argument, which would capture it at import and make the "one named place"
    a lie the moment anything tried to change it — which is exactly what #72
    will want to do.
    """
    if current_for is None:
        current_for = CURRENT_FOR
    row = connection.execute(
        "SELECT at FROM sweep WHERE work_id = ? AND scope = ? AND marketplace = ? "
        "ORDER BY id DESC LIMIT 1",
        (work_id, scope, marketplace),
    ).fetchone()
    if row is None:
        return True
    swept_at = _parse_timestamp(row["at"])
    if swept_at is None:
        return True
    return datetime.now(UTC) - swept_at >= current_for


def swept_at(
    connection: sqlite3.Connection,
    work_id: int,
    *,
    scope: Scope = "us",
    marketplace: Marketplace = "ebay",
) -> datetime | None:
    """When this book was last searched for on this marketplace in this scope."""
    row = connection.execute(
        "SELECT at FROM sweep WHERE work_id = ? AND scope = ? AND marketplace = ? "
        "ORDER BY id DESC LIMIT 1",
        (work_id, scope, marketplace),
    ).fetchone()
    return _parse_timestamp(row["at"]) if row else None


def _parse_timestamp(raw: str | None) -> datetime | None:
    """SQLite's `datetime('now')` is UTC and says so nowhere in the string."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def store(
    connection: sqlite3.Connection,
    work_id: int,
    listings: list[Listing],
    *,
    asked_for: int | None = None,
    scope: Scope = "us",
    marketplace: Marketplace = "ebay",
) -> int:
    """Record what a marketplace just returned, keeping everything seen before.

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
    if scope == "us":
        # Before anything is written, the want list's "from" price as it
        # stands, for the caret that says which way this check moved it
        # (S72). Only US sweeps feed the want list. Imported here because
        # `moves` reads the store through modules that import this one.
        from book_watch import moves

        moves.before_check(connection, work_id, datetime.now(UTC))
    sweep_id = connection.execute(
        "INSERT INTO sweep (work_id, asked_for, total_matching, scope, marketplace) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (work_id, asked_for, getattr(listings, "total", None), scope, marketplace),
    ).fetchone()["id"]

    previous = {
        row["item_id"]: row
        for row in connection.execute(
            "SELECT copy.item_id, copy.price, copy.currency, copy.shipping, "
            "       copy.condition, seen.sweep_id AS last_sweep_id "
            "  FROM copy "
            "  LEFT JOIN copy_seen AS seen "
            "         ON seen.marketplace = copy.marketplace "
            "        AND seen.item_id = copy.item_id "
            "        AND seen.work_id = copy.work_id AND seen.scope = ? "
            " WHERE copy.work_id = ? AND copy.marketplace = ?",
            (scope, work_id, marketplace),
        )
    }
    latest_before = connection.execute(
        "SELECT id, asked_for, total_matching FROM sweep "
        "WHERE work_id = ? AND scope = ? AND marketplace = ? AND id < ? "
        "ORDER BY id DESC LIMIT 1",
        (work_id, scope, marketplace, sweep_id),
    ).fetchone()
    was_current = latest_before["id"] if latest_before else None
    # Whether absence from that sweep was evidence of anything at all.
    saw_everything = latest_before is not None and _was_complete(latest_before)

    fresh: list[str] = []
    for listing in listings:
        shipping = _shipping_of(listing)
        before = previous.get(listing.item_id)
        if before is None:
            fresh.append(listing.item_id)
        else:
            _count_move(marketplace, before, listing, shipping)
        connection.execute(
            """
            INSERT INTO copy (
                marketplace, item_id, work_id, title, url, price, currency,
                shipping, condition, condition_id, seller, thumbnail, epid,
                listed_at, located_in, buying_options, first_seen_at,
                last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      datetime('now'), datetime('now'))
            ON CONFLICT (marketplace, item_id, work_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                price = excluded.price,
                currency = excluded.currency,
                shipping = excluded.shipping,
                condition = excluded.condition,
                condition_id = excluded.condition_id,
                seller = excluded.seller,
                thumbnail = excluded.thumbnail,
                epid = excluded.epid,
                listed_at = excluded.listed_at,
                located_in = excluded.located_in,
                buying_options = excluded.buying_options,
                last_seen_at = datetime('now')
            """,
            (
                marketplace,
                listing.item_id,
                work_id,
                listing.title,
                listing.item_web_url,
                str(listing.price.amount),
                listing.price.currency,
                shipping,
                listing.condition,
                listing.condition_id,
                listing.seller,
                listing.thumbnail_url,
                listing.epid,
                listing.listing_date.isoformat() if listing.listing_date else None,
                listing.located_in,
                json.dumps(list(listing.buying_options))
                if listing.buying_options
                else None,
            ),
        )
        connection.execute(
            "INSERT INTO copy_seen (marketplace, item_id, work_id, scope, sweep_id) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (marketplace, item_id, work_id, scope) DO UPDATE SET "
            "    sweep_id = excluded.sweep_id",
            (marketplace, listing.item_id, work_id, scope, sweep_id),
        )
        if _worth_recording(before, listing, shipping, was_current, saw_everything):
            connection.execute(
                "INSERT INTO sighting (marketplace, item_id, work_id, sweep_id, "
                "price, currency, shipping, condition) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    marketplace,
                    listing.item_id,
                    work_id,
                    sweep_id,
                    str(listing.price.amount),
                    listing.price.currency,
                    shipping,
                    listing.condition,
                ),
            )

    monitoring.check_saw(
        copies=len(listings),
        new=len(fresh),
        full=_filled(asked_for, getattr(listings, "total", None), len(listings)),
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


def check_ebay(
    connection: sqlite3.Connection,
    work_id: int,
    search: Callable[..., list[Listing]],
    query: str,
    limit: int,
    scope: Scope,
) -> int:
    """Search eBay for one book and store what came back, as one check.

    Every check of a book on eBay comes through here, so each writes the same
    `check` line, and a failed search raises after writing it. Returns the
    sweep id.
    """
    with monitoring.check("ebay"):
        return store(
            connection,
            work_id,
            search(query, limit, scope=scope),
            asked_for=limit,
            scope=scope,
        )


def store_both_scopes(
    connection: sqlite3.Connection,
    work_id: int,
    listings: list[Listing],
    *,
    asked_for: int | None = None,
    marketplace: Marketplace,
) -> tuple[int, int]:
    """Record one search that mixes US and foreign sellers as both views.

    eBay's US-only and everywhere views are two searches. A marketplace whose
    one search returns sellers from everywhere feeds both: everywhere gets
    every copy, and US-only gets the copies whose seller is in the US. The
    count of matching listings belongs to the search as a whole, so it is
    kept only on the everywhere sweep. Returns the two sweep ids, everywhere
    first.
    """
    everywhere = store(
        connection,
        work_id,
        listings,
        asked_for=asked_for,
        scope="everywhere",
        marketplace=marketplace,
    )
    us = store(
        connection,
        work_id,
        [listing for listing in listings if is_us(listing.located_in)],
        asked_for=None,
        scope="us",
        marketplace=marketplace,
    )
    return everywhere, us


def _count_move(
    marketplace: Marketplace,
    before: sqlite3.Row,
    listing: Listing,
    shipping: str | None,
) -> None:
    """Count a copy whose delivered price this check moved, and which way.

    In the same currency only, and with shipping only when both prices know
    it, so a change in what is known isn't counted as a move.
    """
    if before["currency"] != listing.price.currency:
        return
    then = Decimal(before["price"])
    now = listing.price.amount
    if before["shipping"] is not None and shipping is not None:
        then += Decimal(before["shipping"])
        now += Decimal(shipping)
    if now != then:
        counts.price_moves.labels(marketplace, "down" if now < then else "up").inc()


def _filled(asked_for: int | None, total: int | None, returned: int) -> bool:
    """Whether a check came back full, so copies past its page went unseen.

    The same rule for every marketplace: more matched than was asked for, or,
    with no count, as many came back as were asked for.
    """
    if asked_for is None:
        return False
    if total is not None:
        return total > asked_for
    return returned >= asked_for


def _was_complete(sweep: sqlite3.Row) -> bool:
    """Did this sweep see every listing that matched, or only a window?

    eBay ranks by relevance and we ask for a fixed number, so a copy can leave
    our results without leaving the market. A sweep only knows it saw
    everything when eBay said how many matched and that number fits inside
    what we asked for — or when eBay returned fewer than we asked for, which
    is the same fact arriving a different way.

    Not knowing counts as a window. That is the conservative reading and it is
    what every other unknown in this project gets.
    """
    asked_for, total = sweep["asked_for"], sweep["total_matching"]
    if asked_for is None or total is None:
        return False
    return total <= asked_for


def _worth_recording(
    before: sqlite3.Row | None,
    listing: Listing,
    shipping: str | None,
    was_current: int | None,
    saw_everything: bool,
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

    **Unless the last sweep only saw a window.** Then the copy's absence from
    it was never evidence of absence — it may have sat at rank 51 the whole
    time — and writing a reappearance would record a gap in the market that
    only ever existed in our results. On a book with more than fifty listings
    the copies at the edge churn in and out on every visit, so this is the
    difference between a price history and a log of eBay's ranking.
    """
    if before is None:
        return True
    if before["last_sweep_id"] != was_current and saw_everything:
        return True  # genuinely absent last time, and now back
    return (
        before["price"] != str(listing.price.amount)
        or before["currency"] != listing.price.currency
        or before["shipping"] != shipping
        or before["condition"] != listing.condition
    )


def price_history(
    connection: sqlite3.Connection,
    work_id: int,
    item_id: str,
    marketplace: Marketplace = "ebay",
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
            "WHERE sighting.work_id = ? AND sighting.marketplace = ? "
            "  AND sighting.item_id = ? "
            "ORDER BY sighting.sweep_id",
            (work_id, marketplace, item_id),
        )
    ]


def _shipping_of(listing: Listing) -> str | None:
    cost = listing.shipping_cost
    if cost is None or cost.currency != listing.price.currency:
        return None
    return str(cost.amount)

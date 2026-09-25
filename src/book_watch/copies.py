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
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from book_watch.ebay.search import Listing, Money, Scope
from book_watch.isbn import normalise
from book_watch.matching import Evidence, Target, Tier, grade, is_this_book
from book_watch.wantlist import Entry

#: Everything the grader needs about one copy, in one query rather than three
#: lookups per row. The joins are left joins throughout: a copy nobody has
#: asked eBay about, and a number nobody has asked Open Library about, are
#: both ordinary states rather than missing data.
#:
#: Unrestricted by sweep: this is every copy of the book we have ever
#: recorded. What is *for sale* is a narrower question, and `_CURRENT_IN_SCOPE`
#: below is what narrows it.
_SELECT = """
SELECT copy.item_id,
       copy.title,
       copy.url,
       copy.price,
       copy.currency,
       copy.shipping,
       copy.condition,
       copy.condition_id,
       copy.seller,
       copy.thumbnail,
       copy.epid,
       copy.located_in,
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


#: Narrows `_SELECT` to what a sweep of one scope saw last time it ran — the
#: page's "what is buyable today". Appended rather than built in, because the
#: same columns answer a second question: what this book has ever been seen
#: at, which is a statement about the market and must not be restricted to
#: the copies that happen to be listed this minute.
#:
#: Scope matters and is not a filter over one set of results: a US-only sweep
#: and an everywhere sweep are different questions, and an everywhere sweep
#: finds *fewer* US copies because imports displace them out of the fifty
#: slots. So a view reads the newest sweep of its own scope rather than
#: filtering one out of the other. The comparison is on a sweep id rather
#: than a time: two sweeps a second apart are different sweeps and a
#: timestamp cannot say so. `IS` rather than `=` so that a book with no sweep
#: at all matches its copies instead of silently showing none.
_CURRENT_IN_SCOPE = """
   AND copy.item_id IN (
       SELECT seen.item_id FROM copy_seen AS seen
        WHERE seen.work_id = ? AND seen.scope = ?
          AND seen.sweep_id IS (
              SELECT sweep.id FROM sweep
               WHERE sweep.work_id = seen.work_id AND sweep.scope = seen.scope
            ORDER BY sweep.id DESC LIMIT 1
          )
   )
"""


#: What a ceiling says about one copy. Three answers rather than two, because
#: a delivered price is not always knowable — and the page distinguishes the
#: two reasons it might not be, since one is the seller's silence about
#: postage and the other is a currency we cannot compare.
Verdict = Literal[
    "under", "over", "shipping unstated", "another currency", "no ceiling"
]

#: Which market a copy belongs to. Not three grades on one scale — new and
#: used are two different markets, priced by different things: a new copy by
#: publisher and distributor economics through bulk sellers, a used copy by
#: scarcity and wear. Pooling them puts a floor under the used number that has
#: nothing to do with the used market.
ConditionClass = Literal["new", "used", "unknown"]

#: eBay's id for a brand-new item. Every other id is some flavour of
#: secondhand, Like New included: it has had an owner, which is the thing that
#: separates the two markets.
_BRAND_NEW = "1000"

#: Why a copy could not be placed among the others, when it could not be.
#: All three are ordinary states rather than errors, and they are told apart
#: because they are different problems — the same reasoning that gives the
#: ceiling two ways of saying "cannot tell" instead of one.
#:
#: "no condition code" is the awkward one and it is why this is three values
#: rather than two. A copy can carry eBay's words without eBay's number: every
#: row recorded before migration 017 does, because the number was parsed and
#: dropped for months. Saying "the seller didn't state a condition" about a
#: copy whose own line reads "Good" would be a visible contradiction, and a
#: page that contradicts itself is not trusted about the things it gets right.
Unplaced = Literal["no delivered price", "condition unstated", "no condition code"]


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
    #: eBay's numeric condition id, kept because the display string beside it
    #: cannot be grouped on. Decision 33 lost seven listings to trusting
    #: eBay's category strings; these are localized and re-worded, and the
    #: number is the part that holds still.
    condition_id: str | None = None
    seller: str | None = None
    thumbnail: str | None = None
    category: str | None = None
    declared_author: str | None = None
    declared_format: str | None = None
    declared_publisher: str | None = None
    declared_year: str | None = None
    #: Two-letter country code, or None when eBay did not say. Only ever used
    #: to mark a copy as coming from abroad, never to hide one: US-only is a
    #: property of the *search*, and by the time a copy is on this page it is
    #: one we asked for.
    located_in: str | None = None
    #: Whether eBay has been asked what this seller declared. False means the
    #: copy is graded on its listing name alone and may firm up later.
    looked_at: bool = True

    @property
    def condition_class(self) -> ConditionClass:
        """Which market this copy is in, from the id and never from the words.

        Unknown when eBay stated no id — which is both a seller who filled
        nothing in and every copy recorded before the id was stored. It is
        left as its own answer rather than folded into used: a copy that might
        be shrink-wrapped and might be water-damaged is not evidence about
        either market.
        """
        if self.condition_id is None:
            return "unknown"
        return "new" if self.condition_id == _BRAND_NEW else "used"

    @property
    def landed_cost(self) -> Money | None:
        """Price plus shipping, or `None` when that cannot be known.

        Same rule as the search client: shipping that was never stated, or
        stated in another currency, gives no total rather than a wrong one.
        """
        if self.shipping is None or self.shipping.currency != self.price.currency:
            return None
        return Money(self.price.amount + self.shipping.amount, self.price.currency)

    def against(self, ceiling: Money | None) -> Verdict:
        """Is this copy within what somebody said they would pay?

        Three answers, not two. "Under" and "over" are not exhaustive, because
        a copy whose shipping eBay never stated has no delivered price at all —
        and the two honest-looking shortcuts are both wrong:

        - treating unstated shipping as free flatters the copy and invents a
          bargain, which is the wasted-trust failure the brief is about;
        - treating it as over is right most of the time and wrong sometimes,
          with no way to tell which times.

        So there is a third answer and the page says which of the two reasons
        produced it.

        This differs on purpose from `sort_key`, which ranks an unknown total
        by its price alone. **A sort has to put the row somewhere; a claim does
        not.** Guessing to order a list is a lesser sin than guessing in an
        assertion the reader will act on.
        """
        if ceiling is None:
            return "no ceiling"
        if self.shipping is None:
            return "shipping unstated"
        landed = self.landed_cost
        if landed is None or landed.currency != ceiling.currency:
            return "another currency"
        return "under" if landed.amount <= ceiling.amount else "over"

    @property
    def sort_key(self) -> Decimal:
        """Cheapest first, with an unknown total ranking as its price alone.

        A copy whose shipping eBay declined to state is not free and not
        infinite. Ranking it by its price is the least wrong of the available
        lies, and the page says which it is.
        """
        landed = self.landed_cost
        return landed.amount if landed else self.price.amount


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
        "SELECT at FROM sweep WHERE work_id = ? AND scope = ? ORDER BY id DESC LIMIT 1",
        (work_id, scope),
    ).fetchone()
    if row is None:
        return True
    swept_at = _parse_timestamp(row["at"])
    if swept_at is None:
        return True
    return datetime.now(UTC) - swept_at >= current_for


def swept_at(
    connection: sqlite3.Connection, work_id: int, *, scope: Scope = "us"
) -> datetime | None:
    """When this book was last searched for in this scope, or None if never."""
    row = connection.execute(
        "SELECT at FROM sweep WHERE work_id = ? AND scope = ? ORDER BY id DESC LIMIT 1",
        (work_id, scope),
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
) -> int:
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
        "INSERT INTO sweep (work_id, asked_for, total_matching, scope) "
        "VALUES (?, ?, ?, ?) RETURNING id",
        (work_id, asked_for, getattr(listings, "total", None), scope),
    ).fetchone()["id"]

    previous = {
        row["item_id"]: row
        for row in connection.execute(
            "SELECT copy.item_id, copy.price, copy.currency, copy.shipping, "
            "       copy.condition, seen.sweep_id AS last_sweep_id "
            "  FROM copy "
            "  LEFT JOIN copy_seen AS seen "
            "         ON seen.item_id = copy.item_id "
            "        AND seen.work_id = copy.work_id AND seen.scope = ? "
            " WHERE copy.work_id = ?",
            (scope, work_id),
        )
    }
    latest_before = connection.execute(
        "SELECT id, asked_for, total_matching FROM sweep "
        "WHERE work_id = ? AND scope = ? AND id < ? ORDER BY id DESC LIMIT 1",
        (work_id, scope, sweep_id),
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
        connection.execute(
            """
            INSERT INTO copy (
                item_id, work_id, title, url, price, currency, shipping,
                condition, condition_id, seller, thumbnail, epid, listed_at,
                located_in, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      datetime('now'), datetime('now'))
            ON CONFLICT (item_id, work_id) DO UPDATE SET
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
                last_seen_at = datetime('now')
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
                listing.condition_id,
                listing.seller,
                listing.thumbnail_url,
                listing.epid,
                listing.listing_date.isoformat() if listing.listing_date else None,
                listing.located_in,
            ),
        )
        connection.execute(
            "INSERT INTO copy_seen (item_id, work_id, scope, sweep_id) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (item_id, work_id, scope) DO UPDATE SET "
            "    sweep_id = excluded.sweep_id",
            (listing.item_id, work_id, scope, sweep_id),
        )
        if _worth_recording(before, listing, shipping, was_current, saw_everything):
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


def for_entry(
    connection: sqlite3.Connection, entry: Entry, *, scope: Scope = "us"
) -> list[Copy]:
    """Every stored copy for this book, graded and cheapest first within a tier.

    Sorting happens **inside** a tier and never across one. A reader sees one
    group today, so this looks like an ordering with an extra step — decision
    33 measured that on the other hunt the cheapest certain copy was wrong,
    and a sort that crossed tiers would have to be unpicked to support it.
    """
    target = _target(connection, entry)
    copies = [
        _to_copy(row, target, entry)
        for row in connection.execute(
            _SELECT + _CURRENT_IN_SCOPE, (entry.work_id, entry.work_id, scope)
        )
    ]
    order = {"certain": 0, "probable": 1, "possible": 2, "excluded": 3}
    copies.sort(key=lambda copy: (order[copy.tier], copy.sort_key))
    return copies


def ever_seen(connection: sqlite3.Connection, entry: Entry) -> list[Copy]:
    """Every copy of this book we have ever recorded, graded, in no order.

    The wider of the two populations, and the one a *range* is taken over. A
    copy that stopped appearing last week still happened: it was a real book
    at a real asking price, and forgetting it the moment it sells would leave
    the range describing only what is currently unsold, which is the slowest-
    moving and most over-priced end of the market.

    Not restricted by scope either. Which search found a copy is a fact about
    us rather than about the book, and a range is a statement about the book.
    """
    target = _target(connection, entry)
    return [
        _to_copy(row, target, entry)
        for row in connection.execute(_SELECT, (entry.work_id,))
    ]


@dataclass(frozen=True, slots=True)
class Standing:
    """Where one copy sits among the others of the same book and kind.

    Two numbers about two different populations, which is the whole point of
    keeping them in one object: a *rank* is about what you could buy instead
    of this, right now, so it counts only copies currently listed — you
    cannot be cheapest of a set including four that are gone. A *range* is
    about what the book asks, so it spans every copy ever seen.
    """

    condition_class: ConditionClass
    #: 1 is cheapest. None when this copy could not be placed, and `unplaced`
    #: then says why.
    rank: int | None = None
    #: Whether something else is asking exactly the same. Without this, two
    #: copies at $9.99 would both read "cheapest of 6" and the page would look
    #: broken rather than tied.
    tied: bool = False
    #: How many copies the rank is out of — currently listed, same class.
    listed: int = 0
    low: Money | None = None
    high: Money | None = None
    #: How many copies the range spans. Always at least `listed`, because
    #: everything listed now has also been seen.
    seen: int = 0
    unplaced: Unplaced | None = None


def standings(listed: list[Copy], seen: list[Copy]) -> dict[str, Standing]:
    """Place each listed copy among the others, by item id.

    **Certain copies only, on both sides.** The possible tier ran at 8–14%
    precision on the edition question (decision 33), so a range averaged
    across it would mostly be other books, and a rank against it would be a
    rank against a different title.

    **Grouped by class and by currency.** The class split is the substantive
    one and decision 51 argues it. The currency split is the same refusal to
    compare that `against` makes: a range from £5 to $36 is not a range, and
    putting a symbol on it would not make it one.

    **Everything is a delivered price.** Price and postage are one number
    here, as they are everywhere else in this project — a $7 book with $6
    postage is a $13 book, and a seller who moves cost from one column to the
    other must not be able to move their copy up the page by doing it.

    Copies that cannot be placed get an entry saying so rather than no entry
    at all. Silence would read as "nothing to report about this copy", when
    what is true is "this copy withheld what the comparison needs".
    """
    listed_prices: dict[tuple[str, str], list[Decimal]] = {}
    seen_prices: dict[tuple[str, str], list[Decimal]] = {}
    for copies_in, prices in ((listed, listed_prices), (seen, seen_prices)):
        for copy in copies_in:
            placed = _placeable(copy)
            if placed is None:
                continue
            prices.setdefault((copy.condition_class, placed.currency), []).append(
                placed.amount
            )

    standing: dict[str, Standing] = {}
    for copy in listed:
        if copy.tier != "certain":
            continue
        kind = copy.condition_class
        if kind == "unknown":
            # Which kind of silence it was. A seller who filled nothing in is
            # a different situation from a copy we recorded before the code
            # was kept, and only the first is the seller's doing.
            standing[copy.item_id] = Standing(
                kind,
                unplaced=(
                    "condition unstated"
                    if copy.condition is None
                    else "no condition code"
                ),
            )
            continue
        delivered = copy.landed_cost
        if delivered is None:
            standing[copy.item_id] = Standing(kind, unplaced="no delivered price")
            continue

        key = (kind, delivered.currency)
        here = sorted(listed_prices.get(key, []))
        everything = seen_prices.get(key, [])
        standing[copy.item_id] = Standing(
            condition_class=kind,
            # Competition ranking: two copies at the same price are both
            # cheapest, and the next one along is third. Handing one of them
            # first place because it sorted higher would be a coin toss
            # presented as a finding.
            rank=here.index(delivered.amount) + 1,
            tied=here.count(delivered.amount) > 1,
            listed=len(here),
            low=Money(min(everything), delivered.currency) if everything else None,
            high=Money(max(everything), delivered.currency) if everything else None,
            seen=len(everything),
        )
    return standing


@dataclass(frozen=True, slots=True)
class Market:
    """One condition class's standing for a book, stated once for the page.

    The same numbers `Standing` carries per copy, lifted to the book. Every
    copy of a class shares its class's range and count, so rendering them per
    copy repeats one fact as many times as there are copies — which is what
    S21 shipped and what reading it made obvious.
    """

    condition_class: ConditionClass
    #: Copies of this class listed now, which is what a rank counts.
    listed: int
    #: Copies of this class ever recorded, which is what a range spans.
    seen: int
    low: Money | None = None
    high: Money | None = None

    @property
    def has_range(self) -> bool:
        """Is there a range worth stating, or only a number wearing a dash?

        One observation is not a range, and neither is two at the same price —
        "asking 18.00–18.00" is a sentence that looks like information.
        """
        if self.low is None or self.high is None:
            return False
        return self.seen > 1 and self.low.amount != self.high.amount


#: Used before new, because the reading hunt is the dominant one and a new
#: copy is usually bulk inventory. *Two kinds of hunt* is where a collectible
#: entry may want this inverted, and when it does the order belongs here
#: rather than in a template.
_MARKET_ORDER: dict[ConditionClass, int] = {"used": 0, "new": 1, "unknown": 2}


def markets(standing: dict[str, Standing]) -> list[Market]:
    """The classes this book's listed copies sit in, one entry each.

    Derived from the per-copy standings rather than from a second query: every
    number is already in there, repeated once per copy, and this is the lift.

    **Only classes with copies listed now appear.** These head a list, so a
    class with nothing in that list has no list to head. A used range for a
    book whose used copies have all gone is a real and interesting fact, and
    it is a different statement from this one — it belongs to whatever shows
    a book's history rather than to a header over what is for sale.

    **Unknown never appears.** It has no range worth stating and no rank to
    head, so the page mentions it only on the copies themselves, where it
    says why that copy could not be placed.

    Keyed by class *and* currency, because `standings` partitions by both: a
    GBP used copy and a USD used copy are not in one market and their prices
    cannot share a range.
    """
    found: dict[tuple[ConditionClass, str], Market] = {}
    for placed in standing.values():
        if placed.rank is None or placed.low is None:
            continue
        found[(placed.condition_class, placed.low.currency)] = Market(
            condition_class=placed.condition_class,
            listed=placed.listed,
            seen=placed.seen,
            low=placed.low,
            high=placed.high,
        )
    return sorted(
        found.values(),
        key=lambda market: (_MARKET_ORDER[market.condition_class], -market.listed),
    )


def _placeable(copy: Copy) -> Money | None:
    """What this copy counts as in a comparison, or None if it cannot count.

    A copy needs three things to be comparable: to be certainly this book, to
    be in a known market, and to have a price somebody could actually pay.
    """
    if copy.tier != "certain" or copy.condition_class == "unknown":
        return None
    return copy.landed_cost


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
        condition_id=row["condition_id"],
        seller=row["seller"],
        thumbnail=row["thumbnail"],
        category=row["category"],
        declared_author=row["declared_author"],
        declared_format=row["declared_format"],
        declared_publisher=row["declared_publisher"],
        declared_year=row["declared_year"],
        located_in=row["located_in"],
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

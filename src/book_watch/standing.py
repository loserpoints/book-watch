"""Where a copy sits among the others of the same book.

Two questions with two different populations, and keeping them apart is most
of what this module is. A **rank** counts copies listed now, because you
cannot be cheapest of a set including four that are gone. A **range** spans
every copy ever recorded, because a copy that has left was still a real book
at a real asking price.

New and used copies pool (S70, #247). For a reader any copy that reads will
do, so condition is something to judge a copy by, not a separate market. A
book's copies split only by currency, since prices in two currencies are
never compared.

Every figure is a delivered price and every figure is an
*asking* price. What a sweep observes is that a copy was listed at a price and
later was not; why it went is not available to us. Nothing here
may imply a copy sold, or sold for this.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from book_watch.copies import Copy, Verdict, is_new, populations
from book_watch.ebay.search import Money, Scope
from book_watch.marketplaces import Marketplace
from book_watch.sweeps import swept_at
from book_watch.wantlist import Entry

#: Why a copy could not be placed among the others, when it could not be. An
#: ordinary state rather than an error. A copy's condition no longer matters
#: here: with new and used pooled, a copy whose seller stated no condition is
#: still a copy at a price.
Unplaced = Literal["no delivered price"]


@dataclass(frozen=True, slots=True)
class Standing:
    """Where one copy sits among the others of the same book.

    Two numbers about two different populations, which is the whole point of
    keeping them in one object: a *rank* is about what you could buy instead
    of this, right now, so it counts only copies currently listed — you
    cannot be cheapest of a set including four that are gone. A *range* is
    about what the book asks, so it spans every copy ever seen.
    """

    #: 1 is cheapest. None when this copy could not be placed, and `unplaced`
    #: then says why.
    rank: int | None = None
    #: Whether something else is asking exactly the same. Without this, two
    #: copies at $9.99 would both read "cheapest of 6" and the page would look
    #: broken rather than tied.
    tied: bool = False
    #: How many copies the rank is out of — currently listed, same currency.
    listed: int = 0
    low: Money | None = None
    high: Money | None = None
    #: How many copies the range spans. Always at least `listed`, because
    #: everything listed now has also been seen.
    seen: int = 0
    unplaced: Unplaced | None = None


def standings(
    listed: list[Copy], seen: list[Copy]
) -> dict[tuple[Marketplace, str], Standing]:
    """Place each listed copy among the others, by item id.

    **Certain copies only, on both sides.** The possible tier ran at 8–14%
    precision on the edition question, so a range averaged
    across it would mostly be other books, and a rank against it would be a
    rank against a different title.

    **Grouped by currency.** The same refusal to compare that `against`
    makes: a range from £5 to $36 is not a range, and putting a symbol on it
    would not make it one. New and used are not split (S70, #247).

    **Everything is a delivered price.** Price and postage are one number
    here, as they are everywhere else in this project — a $7 book with $6
    postage is a $13 book, and a seller who moves cost from one column to the
    other must not be able to move their copy up the page by doing it.

    Copies that cannot be placed get an entry saying so rather than no entry
    at all. Silence would read as "nothing to report about this copy", when
    what is true is "this copy withheld what the comparison needs".
    """
    listed_prices, seen_prices = prices(listed), prices(seen)

    standing: dict[tuple[Marketplace, str], Standing] = {}
    for copy in listed:
        if copy.tier != "certain":
            continue
        delivered = copy.landed_cost
        if delivered is None:
            standing[copy.key] = Standing(unplaced="no delivered price")
            continue

        here = sorted(listed_prices.get(delivered.currency, []))
        everything = seen_prices.get(delivered.currency, [])
        standing[copy.key] = Standing(
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


def prices(copies_in: list[Copy]) -> dict[str, list[Decimal]]:
    """Delivered prices by currency — the populations a rank and a range are
    drawn from.

    Public so a page can draw those populations (the strips) from the same
    derivation that ranked them, rather than a second one that could drift.
    """
    found: dict[str, list[Decimal]] = {}
    for copy in copies_in:
        placed = _placeable(copy)
        if placed is None:
            continue
        found.setdefault(placed.currency, []).append(placed.amount)
    return found


@dataclass(frozen=True, slots=True)
class Market:
    """A book's copies in one currency, stated once for the page.

    The same numbers `Standing` carries per copy, lifted to the book. Every
    copy shares the range and count, so rendering them per copy repeats one
    fact as many times as there are copies — which is what S21 shipped and
    what reading it made obvious.
    """

    #: Copies listed now, which is what a rank counts.
    listed: int
    #: Copies ever recorded, which is what a range spans.
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


def markets(standing: dict[tuple[Marketplace, str], Standing]) -> list[Market]:
    """The currencies this book's listed copies are priced in, one entry each.

    Derived from the per-copy standings rather than from a second query: every
    number is already in there, repeated once per copy, and this is the lift.

    **Only currencies with copies listed now appear.** These head a list, so
    a currency with nothing in that list has no list to head.

    Keyed by currency, because `standings` partitions by it: a GBP copy and a
    USD copy cannot share a range. Most listed first.
    """
    found: dict[str, Market] = {}
    for placed in standing.values():
        if placed.rank is None or placed.low is None:
            continue
        found[placed.low.currency] = Market(
            listed=placed.listed,
            seen=placed.seen,
            low=placed.low,
            high=placed.high,
        )
    return sorted(found.values(), key=lambda market: -market.listed)


@dataclass(frozen=True, slots=True)
class Headline:
    """The one thing the want-list says about a book without opening it.

    One currency's copies, not every currency's. A list is read at a glance,
    and two lines a book is a table rather than a glance — so this picks the
    copies that answer "is there anything worth buying" and leaves the rest
    to the page.
    """

    market: Market
    #: Cheapest delivered price listed in that currency right now.
    cheapest: Money
    #: How that stands against this entry's ceiling. Independent of the rank
    #: above it: the ceiling is about you, the market is not.
    verdict: Verdict


def headline(
    listed: list[Copy],
    standing: dict[tuple[Marketplace, str], Standing],
    ceiling: Money | None,
) -> Headline | None:
    """Pick the copies worth leading with, and the copy that leads them.

    The cheapest copy, new or used (S70, #247). **A currency with a copy under
    the limit leads**, as the morning email counts any copy under it.
    Otherwise the currency with the most copies listed.

    None when there is nothing to lead with: no copies listed, or none that
    can be placed. The row then says what it does know rather than inventing
    a headline.
    """
    leads = [_lead(market, listed, standing, ceiling) for market in markets(standing)]
    if not leads:
        return None
    under = next((lead for lead in leads if lead and lead.verdict == "under"), None)
    return under or leads[0]


def _lead(
    market: Market,
    listed: list[Copy],
    standing: dict[tuple[Marketplace, str], Standing],
    ceiling: Money | None,
) -> Headline | None:
    """The cheapest copy in one currency, as a headline, or None if unpriced."""
    assert market.low is not None  # a market exists only where a price did
    cheapest = {
        key
        for key, placed in standing.items()
        if placed.rank == 1
        and placed.low is not None
        and placed.low.currency == market.low.currency
    }
    # Ties share rank 1 and share a price, so either will do.
    copy = next((one for one in listed if one.key in cheapest), None)
    if copy is None or copy.landed_cost is None:
        return None
    return Headline(
        market=market, cheapest=copy.landed_cost, verdict=copy.against(ceiling)
    )


@dataclass(frozen=True, slots=True)
class Glance:
    """One book as the want-list shows it, read entirely from the store.

    No request is made to build this. The list renders from what the last
    sweep left behind, and checking is a separate, explicit act.
    """

    #: When this book was last searched in this scope, or None if never. The
    #: difference between "nothing is listed" and "nobody has looked" is the
    #: whole reason this is here.
    checked: datetime | None
    #: Copies certainly this book, listed now. Shown when there is no
    #: headline, because a count is still something the reader can use.
    listed: int
    #: Copies carrying the title with nothing to prove the book, which the
    #: page files under "might be this book". Counted separately because
    #: "nothing listed" said over five uncertain copies is simply false —
    #: they are on the market, we just cannot swear they are this book.
    uncertain: int
    headline: Headline | None
    #: Every asking price seen, by currency, for the list's price
    #: strip (S34, #76). The same populations `standings` ranked, so the strip
    #: cannot disagree with the rank. Empty until something is placeable.
    seen_prices: dict[str, list[Decimal]] = field(default_factory=dict)
    #: Copies certainly this book that appeared since I last opened it (S39).
    new: int = 0


def glance(
    connection: sqlite3.Connection, entry: Entry, *, scope: Scope = "us"
) -> Glance:
    """What to show for one book on the want-list. Reads the store only."""
    here, seen = populations(connection, entry, scope=scope)
    standing = standings(here, seen)
    return Glance(
        checked=swept_at(connection, entry.work_id, scope=scope),
        listed=sum(1 for one in here if one.tier == "certain"),
        uncertain=sum(1 for one in here if one.tier not in ("certain", "excluded")),
        headline=headline(here, standing, entry.will_pay),
        seen_prices=prices(seen),
        new=sum(
            1
            for one in here
            if one.tier == "certain" and is_new(one, entry.last_looked)
        ),
    )


def _placeable(copy: Copy) -> Money | None:
    """What this copy counts as in a comparison, or None if it cannot count.

    A copy needs two things to be comparable: to be certainly this book, and
    to have a price somebody could actually pay.
    """
    if copy.tier != "certain":
        return None
    return copy.landed_cost

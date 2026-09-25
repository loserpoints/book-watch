"""Where a copy sits among the others of the same book.

Two questions with two different populations, and keeping them apart is most
of what this module is. A **rank** counts copies listed now, because you
cannot be cheapest of a set including four that are gone. A **range** spans
every copy ever recorded, because a copy that has left was still a real book
at a real asking price (decision 53).

New and used never pool. They are two markets rather than two grades on one
scale — a new copy priced by distributor economics through bulk sellers, a
used one by scarcity and wear — so mixing them puts a floor under the used
number that has nothing to do with the used market (decision 52).

Every figure is a delivered price (decision 51) and every figure is an
*asking* price. What a sweep observes is that a copy was listed at a price and
later was not; why it went is not available to us (decision 47). Nothing here
may imply a copy sold, or sold for this.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from book_watch.copies import ConditionClass, Copy, Verdict, populations
from book_watch.ebay.search import Money, Scope
from book_watch.sweeps import swept_at
from book_watch.wantlist import Entry

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


@dataclass(frozen=True, slots=True)
class Headline:
    """The one thing the want-list says about a book without opening it.

    One market, not all of them. A list is read at a glance, and two lines a
    book is a table rather than a glance — so this picks the market that
    answers "is there anything worth buying" and leaves the rest to the page.
    """

    market: Market
    #: Cheapest delivered price listed in that market right now.
    cheapest: Money
    #: How that stands against this entry's ceiling. Independent of the rank
    #: above it: the ceiling is about you, the market is not.
    verdict: Verdict


def headline(
    listed: list[Copy], standing: dict[str, Standing], ceiling: Money | None
) -> Headline | None:
    """Pick the market worth leading with, and the copy that leads it.

    **Used first, falling back to new.** The reading hunt is the dominant one
    and a new copy is usually bulk inventory, so a used copy is what the list
    is watching for. A book with no used copies at all shows the new market
    instead rather than showing nothing — *State of Grace* is five copies, all
    Brand New, and "nothing listed" would be false.

    `markets` already orders used before new, so this takes the first and the
    fallback costs nothing. When *Two kinds of hunt* inverts the order for a
    collectible entry, it inverts there and this follows.

    None when there is nothing to lead with: no copies listed, or none that
    can be placed. The row then says what it does know rather than inventing
    a headline.
    """
    available = markets(standing)
    if not available:
        return None
    leading = available[0]
    assert leading.low is not None  # a market exists only where a price did

    cheapest = {
        item_id
        for item_id, placed in standing.items()
        if placed.rank == 1
        and placed.condition_class == leading.condition_class
        and placed.low is not None
        and placed.low.currency == leading.low.currency
    }
    # Ties share rank 1 and share a price, so either will do.
    copy = next((one for one in listed if one.item_id in cheapest), None)
    if copy is None or copy.landed_cost is None:
        return None
    return Headline(
        market=leading, cheapest=copy.landed_cost, verdict=copy.against(ceiling)
    )


@dataclass(frozen=True, slots=True)
class Glance:
    """One book as the want-list shows it, read entirely from the store.

    No request is made to build this. The list renders from what the last
    sweep left behind, and checking is a separate, explicit act — decision 54.
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
    )


def _placeable(copy: Copy) -> Money | None:
    """What this copy counts as in a comparison, or None if it cannot count.

    A copy needs three things to be comparable: to be certainly this book, to
    be in a known market, and to have a price somebody could actually pay.
    """
    if copy.tier != "certain" or copy.condition_class == "unknown":
        return None
    return copy.landed_cost

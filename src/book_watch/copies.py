"""Copies offered for sale, and which of them are certainly this book.

A *copy* is one object in one seller's hands at one price. A work has many
editions and an edition has many copies, which is why this is not called
"listing": the word has to survive a second marketplace, and "copy" is what a
person is actually buying.

This module answers "what is for sale, and is it the right book". What a
sweep *recorded* lives in `sweeps`, and where a copy sits among the others in
`standing` — they were one module until it reached 971 lines and five jobs.

Everything here is derived on read (decision 43). Which numbers count as this
book is a query over things we observed, never a conclusion somebody stored,
so changing a rule re-judges every book on the next page view for nothing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from book_watch.ebay.search import Money, Scope
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


def for_entry(
    connection: sqlite3.Connection, entry: Entry, *, scope: Scope = "us"
) -> list[Copy]:
    """Every stored copy for this book, graded and cheapest first within a tier.

    Sorting happens **inside** a tier and never across one. A reader sees one
    group today, so this looks like an ordering with an extra step — decision
    33 measured that on the other hunt the cheapest certain copy was wrong,
    and a sort that crossed tiers would have to be unpicked to support it.
    """
    return _listed(connection, entry, _target(connection, entry), scope)


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
    return _seen(connection, entry, _target(connection, entry))


def populations(
    connection: sqlite3.Connection, entry: Entry, *, scope: Scope = "us"
) -> tuple[list[Copy], list[Copy]]:
    """Both populations a judgement needs, from **one** derivation of the target.

    A rank reads what is listed and a range reads everything seen, so anything
    that judges a book needs both — and calling `for_entry` and `ever_seen`
    beside each other derives the edition set twice, which is two of the seven
    queries a book costs. Deriving it once is not a speed fix: a ten-book
    want-list renders in about 12ms either way. It is that a reader of those
    two lines has to wonder whether the second derivation could disagree with
    the first, and the answer should be that there is only one.

    Returned in the order a page needs them: what is buyable, then everything
    that ever was.
    """
    target = _target(connection, entry)
    return _listed(connection, entry, target, scope), _seen(connection, entry, target)


def _listed(
    connection: sqlite3.Connection, entry: Entry, target: Target, scope: Scope
) -> list[Copy]:
    """Graded and cheapest first **within** a tier, never across one."""
    found = _read(
        connection,
        _SELECT + _CURRENT_IN_SCOPE,
        (entry.work_id, entry.work_id, scope),
        target,
        entry,
    )
    order = {"certain": 0, "probable": 1, "possible": 2, "excluded": 3}
    found.sort(key=lambda copy: (order[copy.tier], copy.sort_key))
    return found


def _seen(connection: sqlite3.Connection, entry: Entry, target: Target) -> list[Copy]:
    return _read(connection, _SELECT, (entry.work_id,), target, entry)


def _read(
    connection: sqlite3.Connection,
    query: str,
    params: tuple,
    target: Target,
    entry: Entry,
) -> list[Copy]:
    return [_to_copy(row, target, entry) for row in connection.execute(query, params)]


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


def _amount(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError):
        # A hand-edited row should not take the page down.
        return Decimal(0)

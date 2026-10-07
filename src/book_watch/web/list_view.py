"""What the want-list hands the system's book row (S34, #98).

The want-list's half of what `book_view` is for the book page: the app's own
objects turned, once, into the plain values `ui.book_row` takes. Nothing here
decides anything; every verdict and number was derived in `standing`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from book_watch import covers, enrichment, marketplaces, moves
from book_watch.purchases import Purchase, total
from book_watch.standing import Glance
from book_watch.wantlist import Entry
from book_watch.web import book_view, strips
from book_watch.web.filters import since

#: The strip beside the price on a want-list row, as S27 drew it.
ROW_STRIP_WIDTH = 104


def added(entry: Entry) -> datetime | None:
    """When the book went on the list. SQLite writes UTC without saying so."""
    try:
        return datetime.fromisoformat(entry.added_at).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def examining(entry: Entry, throttled: bool = False) -> str | None:
    """What the row says about the work of examining its copies.

    "digging" only while a pass is running or about to, since a row that says
    it is working has to be. "throttled" when the pass cannot run because
    Open Library's daily ceiling is spent. Nothing otherwise: the next check
    starts the pass again.
    """
    if not entry.being_enriched:
        return None
    if enrichment.busy(entry.work_id):
        return "digging"
    return "throttled" if throttled else None


def row(
    entry: Entry, glance: Glance | None, state: str = "idle", throttled: bool = False
) -> dict:
    """One book, as `ui.book_row` takes it.

    `state` is the walk's: idle, checking or failed. The row's own state says
    which of the facts S26 kept apart this is — never one said in another's
    words: nobody has looked, nothing is listed, copies are listed but none
    can be compared, only maybes, and here is the cheapest.

    **One working state** (S68, #240). From the moment its book is searched
    until its copies are examined, a row says "digging" in place of its
    counts, which are not true until then, and keeps its last price.
    """
    values = {
        "id": entry.id,
        "href": f"/book/{entry.id}",
        "title": entry.name,
        "author": entry.author,
        "cover_url": _cover(entry),
        "added": since(added(entry)),
        "examining": examining(entry, throttled),
        "state": "unchecked",
        "checking": state == "checking",
    }
    values["working"] = values["checking"] or values["examining"] == "digging"
    if state == "failed":
        return {**values, "state": state}
    if glance is None or glance.checked is None:
        return values
    values["checked"] = since(glance.checked)
    lead = glance.headline
    if lead is not None:
        return {
            **values,
            "state": "ok",
            # Every certain copy, as "new" counts, so new is never more than
            # listed. A copy with no delivered price is listed, unranked.
            "listed": glance.listed,
            "new": glance.new,
            **_price(entry, glance),
        }
    if glance.listed:
        # Copies, but nothing comparable yet: a count is still worth having.
        return {**values, "state": "ok", "listed": glance.listed, "new": glance.new}
    if glance.uncertain:
        return {**values, "state": "maybes", "maybes": glance.uncertain}
    return {**values, "state": "none"}


def _price(entry: Entry, glance: Glance) -> dict:
    """The cheapest copy of the leading market, and the shape of that market.

    The strip is drawn only when there are at least two different prices:
    one price is a point, not a shape (#76's floor). Every dot is one copy
    ever seen, certain and in this market only.
    """
    lead = glance.headline
    assert lead is not None
    ceiling = entry.will_pay
    cheapest = lead.cheapest
    verdict = None
    if lead.verdict == "under":
        verdict = "under"
    elif lead.verdict == "over" and ceiling is not None:
        verdict = "over"
    seen = glance.seen_prices.get(cheapest.currency, [])
    strip = None
    if lead.market.has_range:
        limit = (
            ceiling.amount
            if ceiling is not None and ceiling.currency == cheapest.currency
            else None
        )
        strip = strips.range_strip(
            seen,
            limit,
            width=ROW_STRIP_WIDTH,
            symbol=book_view.SYMBOLS.get(cheapest.currency, ""),
        )
    moved = moves.of_from(entry, cheapest)
    return {
        "price_text": book_view.money(cheapest),
        "verdict": verdict,
        # Which way the latest check moved it, and from what (S72).
        "move": moved.direction if moved else None,
        "was_text": book_view.money(moved.was) if moved else None,
        "strip": strip,
        # Where "$X over" was (S61): the limit itself, or that there is none.
        "limit_text": f"your limit: {book_view.money(ceiling)}"
        if ceiling is not None
        else "no limit set",
    }


def _cover(entry: Entry) -> str | None:
    """Open Library's image when its id is known, our route that learns it
    when it is not, and nothing when there is none."""
    if entry.cover:
        return covers.url(entry.cover)
    return None if entry.has_no_cover else f"/books/{entry.id}/cover"


def candidate(found, on_list: set[str]) -> dict:
    """One Open Library search result, as `ui.candidate_row` takes it, with
    the fields the add form posts back (one user, so the form
    carries them rather than a second request fetching them again)."""
    author = ", ".join(found.authors) or None
    return {
        "title": found.title,
        "author": author,
        "year": found.first_published,
        "editions": found.edition_count,
        "cover_url": covers.url(found.cover_id) if found.cover_id else None,
        "on_list": found.work_id in on_list,
        "post": {
            "title": found.title,
            "author": author or "",
            "work_id": found.work_id,
            "cover_id": found.cover_id or "",
        },
    }


def bought_row(purchase: Purchase, today: date | None = None) -> dict:
    """One book bought, as `ui.bought_row` takes it (S71, #223): what was
    paid, judged against the limit it had then, and where and when."""
    today = today or datetime.now(UTC).date()
    on = purchase.bought_on
    when = f"{on:%b} {on.day}" + (f", {on.year}" if on.year != today.year else "")
    where = (
        marketplaces.NAMES[purchase.marketplace]
        if purchase.marketplace
        else purchase.shop
    )
    return {
        "title": purchase.title,
        "author": purchase.author,
        "cover_url": covers.url(purchase.cover_id) if purchase.cover_id else None,
        "paid_text": book_view.money(purchase.paid),
        "verdict": purchase.verdict,
        "limit_text": f"your limit: {book_view.money(purchase.limit)}"
        if purchase.limit is not None
        else "no limit set",
        "where_when": f"on {where} · {when}",
    }


def bought_total(purchases: list[Purchase]) -> str | None:
    """ "Bought · 3 books · $26.95", the folded section's label. The total is
    left out when the books were paid for in more than one currency."""
    if not purchases:
        return None
    count = len(purchases)
    parts = ["Bought", f"{count} book{'' if count == 1 else 's'}"]
    spent = total(purchases)
    if spent is not None:
        parts.append(book_view.money(spent))
    return " · ".join(parts)

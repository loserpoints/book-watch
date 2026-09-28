"""What the want-list hands the system's book row (S34, #98).

The want-list's half of what `book_view` is for the book page: the app's own
objects turned, once, into the plain values `ui.book_row` takes. Nothing here
decides anything; every verdict and number was derived in `standing`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from book_watch import covers
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


def row(entry: Entry, glance: Glance | None, state: str = "idle") -> dict:
    """One book, as `ui.book_row` takes it.

    `state` is the walk's: idle, checking or failed. The row's own state says
    which of the facts S26 kept apart this is — never one said in another's
    words: nobody has looked, nothing is listed, copies are listed but none
    can be compared, only maybes, and here is the cheapest.
    """
    values = {
        "id": entry.id,
        "href": f"/book/{entry.id}",
        "title": entry.name,
        "author": entry.author,
        "cover_url": _cover(entry),
        "added": since(added(entry)),
        "digging": entry.being_enriched,
        "state": "unchecked",
    }
    if state in ("checking", "failed"):
        return {**values, "state": state}
    if glance is None or glance.checked is None:
        return values
    values["checked"] = since(glance.checked)
    lead = glance.headline
    if lead is not None:
        return {
            **values,
            "state": "ok",
            "listed": lead.market.listed,
            **_price(entry, glance),
        }
    if glance.listed:
        # Copies, but nothing comparable yet: a count is still worth having.
        return {**values, "state": "ok", "listed": glance.listed}
    if glance.uncertain:
        return {**values, "state": "maybes", "maybes": glance.uncertain}
    return {**values, "state": "none"}


def _price(entry: Entry, glance: Glance) -> dict:
    """The cheapest copy of the leading market, and the shape of that market.

    The strip is drawn only when there are at least two different prices:
    one price is a point, not a shape (#76's floor). Every dot is one copy
    ever seen, certain and in this market only (decisions 47, 52, 53).
    """
    lead = glance.headline
    assert lead is not None
    ceiling = entry.will_pay
    cheapest = lead.cheapest
    verdict, over_by = None, None
    if lead.verdict == "under":
        verdict = "under"
    elif lead.verdict == "over" and ceiling is not None:
        verdict = "over"
        over_by = book_view.money(cheapest.amount - ceiling.amount, ceiling.currency)
    seen = glance.seen_prices.get((lead.market.condition_class, cheapest.currency), [])
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
    return {
        "price_text": book_view.money(cheapest),
        "verdict": verdict,
        "over_by": over_by,
        "strip": strip,
    }


def _cover(entry: Entry) -> str | None:
    """Open Library's image when its id is known, our route that learns it
    when it is not, and nothing when there is none (decision 56)."""
    if entry.cover:
        return covers.url(entry.cover)
    return None if entry.has_no_cover else f"/books/{entry.id}/cover"

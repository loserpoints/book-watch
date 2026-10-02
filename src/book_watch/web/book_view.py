"""What the book page hands the system's pieces (S34, #98).

The macros in `templates/_ui.html` take plain values so `/design` can draw
them from samples. This is the other half: the app's own objects turned into
those values, once, here, so the template only lays them out.

Nothing here decides anything new. Every verdict, rank and range is the one
`copies` and `standing` already derived; this only chooses how
each is written down.
"""

from __future__ import annotations

from decimal import Decimal

from markupsafe import Markup

from book_watch.copies import Copy, Verdict
from book_watch.ebay.search import Money
from book_watch.standing import Market, Standing
from book_watch.web import strips
from book_watch.web.filters import since

SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}

#: The market strip spans the phone's content width (360 less the gutters).
MARKET_STRIP_WIDTH = 328

Prices = dict[tuple[str, str], list[Decimal]]


def money(value: Money | Decimal, currency: str = "USD") -> str:
    """$12.98, or $12 when there are no cents. A currency without a symbol
    here is written after the number rather than guessed at."""
    amount, code = (
        (value.amount, value.currency)
        if isinstance(value, Money)
        else (value, currency)
    )
    text = f"{amount:.0f}" if amount == amount.to_integral_value() else f"{amount:.2f}"
    symbol = SYMBOLS.get(code)
    return f"{symbol}{text}" if symbol else f"{text} {code}"


def copy_row(
    copy: Copy,
    verdict: Verdict,
    placed: Standing | None,
    ceiling: Money | None,
    listed: Prices,
    new: bool = False,
) -> dict:
    """One copy, as `ui.copy_row` takes it."""
    delivered = copy.landed_cost
    place = _place(copy, placed, listed)
    return {
        "url": copy.url,
        "new": new,
        "listing_title": copy.title,
        "photo_url": copy.thumbnail,
        "photos": list(copy.photos),
        "note": copy.condition_note,
        "condition": copy.condition or "condition unstated",
        "seller": copy.seller or "The seller",
        "edition": " · ".join(
            part
            for part in (
                copy.declared_format,
                copy.declared_publisher,
                copy.declared_year,
            )
            if part
        )
        or None,
        "abroad": copy.located_in
        if copy.located_in and copy.located_in != "US"
        else None,
        "takes_offers": copy.takes_offers,
        # When eBay first listed it (S62), kept through a relist. No date
        # means no age, never an age of zero.
        "listed": since(copy.listed) if copy.listed else None,
        # Delivered when it can be known; otherwise the asking
        # price, and the row says shipping is unknown rather than implying it.
        "price_text": money(delivered) if delivered else money(copy.price),
        "shipping_unknown": delivered is None and copy.shipping is None,
        **_against(copy, verdict, ceiling),
        **place,
    }


def _against(copy: Copy, verdict: Verdict, ceiling: Money | None) -> dict:
    """Under or over the limit. A copy that can't be told, or has no limit
    to be told against, is left uncolored. How far over is not said (S61):
    the strip shows where the limit sits."""
    if verdict == "under":
        return {"verdict": "under"}
    if verdict == "over" and ceiling is not None and copy.landed_cost is not None:
        return {"verdict": "over"}
    return {"verdict": None}


def _place(copy: Copy, placed: Standing | None, listed: Prices) -> dict:
    """Where this copy sits among the others of its kind listed now."""
    if placed is None:
        return {"place": None, "place_text": None}
    if placed.unplaced is not None:
        return {"place": None, "place_text": f"can't place: {placed.unplaced}"}
    if placed.listed == 1:
        return {"place": None, "place_text": f"only {placed.condition_class} listing"}
    delivered = copy.landed_cost
    assert delivered is not None  # placed, so it had a delivered price
    peers = listed.get((placed.condition_class, delivered.currency), [])
    return {"place": strips.rank_strip(peers, delivered.amount), "place_text": None}


def market_line(market: Market, seen: Prices, ceiling: Money | None) -> dict:
    """One market, as `ui.market` takes it: what is listed now, and the strip
    of every asking price ever seen, with the limit where it applies."""
    # Two populations, both named: what a rank counts, and what
    # the strip spans. "Seen" is left off when it would repeat the count.
    words = f"{market.listed} {market.condition_class} listed now"
    if market.seen > market.listed:
        words += f", {market.seen} seen"
    currency = market.low.currency if market.low else "USD"
    prices = seen.get((market.condition_class, currency), [])
    strip: Markup | None = None
    if market.has_range:
        limit = (
            ceiling.amount
            if ceiling is not None and ceiling.currency == currency
            else None
        )
        strip = strips.range_strip(
            prices,
            limit,
            width=MARKET_STRIP_WIDTH,
            height=20,
            symbol=SYMBOLS.get(currency, ""),
        )
    return {"text": words, "strip": strip}

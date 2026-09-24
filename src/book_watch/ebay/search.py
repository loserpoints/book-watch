"""Search the eBay Browse API for listings.

One request per search, no paging. That is not a simplification to fix later:
a want-list entry that needs more than the first page of results is a search
that is too broad to be useful, and the answer is a better query rather than
more pages.

Money is `Decimal`, never `float`. eBay sends prices as strings precisely so
they survive the trip, and parsing "8.99" into a binary float to add shipping
to it would throw that away on the first arithmetic operation.

Run it directly to see what comes back:

    uv run python -m book_watch.ebay.search 9780099448396
    uv run python -m book_watch.ebay.search 9780099448396 --gtin
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx

from book_watch.config import MissingCredentialError, load_ebay_credentials
from book_watch.ebay.auth import (
    DEFAULT_TIMEOUT_SECONDS,
    USER_AGENT,
    EbayTokenProvider,
)
from book_watch.ebay.errors import EbayAuthError, EbaySearchError

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

#: Which of eBay's regional sites to search. Every Browse request must name
#: one; there is no "everywhere".
DEFAULT_MARKETPLACE_ID = "EBAY_US"

DEFAULT_LIMIT = 50

#: eBay rejects anything larger on `item_summary/search`.
MAX_LIMIT = 200

#: How to read the search term. `keyword` puts it in `q`, which matches title
#: and description text. `gtin` asks eBay to treat it as a trade item number,
#: which an ISBN-13 is. Which of these finds more real copies is the open
#: question this module exists to settle — hence the flag on the CLI.
SearchBy = Literal["keyword", "gtin"]


@dataclass(frozen=True, slots=True)
class Money:
    """An amount and the currency it is in, kept together deliberately.

    Separating them is how a tool ends up adding pounds to dollars and
    presenting the total as a saving.
    """

    amount: Decimal
    currency: str

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"


@dataclass(frozen=True, slots=True)
class Listing:
    """One copy offered for sale.

    Optional fields are optional because eBay genuinely omits them, not as a
    convenience. `shipping_cost` in particular must stay three-valued: a
    `Money` of zero means the seller ships free, `None` means eBay told us
    nothing. Collapsing those two is the kind of error that silently ranks an
    expensive copy first and never looks wrong on screen.

    `seller` is a username rather than a required field: a listing with no
    seller named is odd but still buyable, so it does not meet the bar that
    makes a missing id or price fatal.
    """

    item_id: str
    title: str
    price: Money
    item_web_url: str
    #: eBay's own product id, where its catalogue matched this listing to one.
    #: Decision 33: it is one of three identifier signals and the least
    #: trustworthy — it over-merges, so distinct Crash editions share one —
    #: but it finds 80% of the copies of a given edition, which nothing else
    #: does. Absent on about a fifth of used-book listings.
    epid: str | None = None
    condition: str | None = None
    condition_id: str | None = None
    seller: str | None = None
    shipping_cost: Money | None = None
    thumbnail_url: str | None = None
    listing_date: datetime | None = None

    @property
    def landed_cost(self) -> Money | None:
        """What this copy actually costs, or `None` when that is unknowable.

        The brief ranks reading copies on landed cost rather than price, so
        this is the number that matters. It returns `None` rather than
        guessing when shipping is unstated, and also when the two amounts are
        in different currencies — a sum across currencies would be a fiction,
        and a fiction with a currency symbol on it is worse than a blank.
        """
        shipping = self.shipping_cost
        if shipping is None or shipping.currency != self.price.currency:
            return None
        return Money(self.price.amount + shipping.amount, self.price.currency)


class BrowseClient:
    """Searches the Browse API, reusing one token and one connection.

    Shaped like `EbayTokenProvider` on purpose, including who owns the HTTP
    client: pass one in and it is yours to close, let this build one and it
    closes it. The web app will hold a single instance for its lifetime, so
    the token cache in the provider actually does its job.
    """

    def __init__(
        self,
        tokens: EbayTokenProvider,
        *,
        client: httpx.Client | None = None,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    ) -> None:
        self._tokens = tokens
        self._marketplace_id = marketplace_id
        if client is None:
            client = httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
            self._owns_client = True
        else:
            self._owns_client = False
        self._client = client

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        search_by: SearchBy = "keyword",
    ) -> Results:
        """Return the listings matching `query`, newest-first ordering unset.

        Ordering is left to eBay here. Ranking is a decision for the app, and
        doing it in the client would bake one use case's preference into the
        layer both modes share.
        """
        term = query.strip()
        if not term:
            raise EbaySearchError("A search needs a non-empty query.")
        if not 1 <= limit <= MAX_LIMIT:
            raise EbaySearchError(
                f"limit must be between 1 and {MAX_LIMIT}; got {limit}."
            )

        params: dict[str, str | int] = {"limit": limit}
        params["gtin" if search_by == "gtin" else "q"] = term

        try:
            response = self._client.get(
                SEARCH_URL, params=params, headers=self._headers()
            )
        except httpx.HTTPError as exc:
            raise EbaySearchError(
                f"Could not reach the eBay Browse API: {exc}"
            ) from exc

        if response.status_code != httpx.codes.OK:
            raise EbaySearchError(_describe_failure(response))

        return _parse_listings(response)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens.token().value}",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    def close(self) -> None:
        """Close the HTTP client, but only if this object created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> BrowseClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def search_listings(
    query: str,
    limit: int = DEFAULT_LIMIT,
    *,
    search_by: SearchBy = "keyword",
) -> list[Listing]:
    """Search eBay for `query`, building a client and throwing it away.

    For one-shot use — the CLI below, and a REPL. Anything that searches more
    than once should hold a `BrowseClient`, because this mints a fresh token
    every call and so spends the daily budget on authentication.
    """
    credentials = load_ebay_credentials()
    with EbayTokenProvider(credentials) as tokens, BrowseClient(tokens) as browse:
        return browse.search(query, limit=limit, search_by=search_by)


class Results(list[Listing]):
    """The listings that came back, and how many eBay says matched in all.

    A list, so every caller that only wants the listings is unaffected. The
    extra fact matters to exactly one of them: we ask for 50 and eBay ranks by
    relevance, so a copy can sit at rank 51 today and rank 49 tomorrow without
    anything about it changing. A sweep that saw a window is not evidence about
    what is outside the window, and `total` is how a sweep knows which it was.

    `total` is None when eBay did not say. Not zero, and not "we saw
    everything" — unknown, which the reader treats as the window case.
    """

    __slots__ = ("total",)

    def __init__(self, listings: list[Listing], total: int | None = None) -> None:
        super().__init__(listings)
        self.total = total


def _parse_listings(response: httpx.Response) -> Results:
    payload = _decode_json(response)
    summaries = payload.get("itemSummaries")
    total = payload.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        total = None

    # No matches at all: eBay omits the key rather than sending an empty list.
    if summaries is None:
        return Results([], total)
    if not isinstance(summaries, list):
        raise EbaySearchError(
            f"Expected itemSummaries to be a list, got {type(summaries).__name__}"
        )

    return Results(
        [_parse_listing(item, index) for index, item in enumerate(summaries)], total
    )


def _parse_listing(item: Any, index: int) -> Listing:
    """Build one `Listing`, refusing rather than guessing.

    A summary missing an id, a title, a price or a link is not a copy anyone
    can buy, so it is an error rather than something to drop quietly. There is
    no logging in this app yet, and a silent skip would turn an API shape
    change into results that are merely, invisibly, short.
    """
    if not isinstance(item, dict):
        raise EbaySearchError(
            f"Listing {index} was {type(item).__name__}, not an object."
        )

    return Listing(
        item_id=_require_str(item, "itemId", index),
        title=_require_str(item, "title", index),
        price=_require_money(item.get("price"), "price", index),
        epid=_optional_str(item.get("epid")),
        item_web_url=_require_str(item, "itemWebUrl", index),
        condition=_optional_str(item.get("condition")),
        condition_id=_optional_str(item.get("conditionId")),
        seller=_parse_seller(item.get("seller")),
        shipping_cost=_parse_shipping(item.get("shippingOptions"), index),
        thumbnail_url=_parse_thumbnail(item),
        listing_date=_parse_date(item.get("itemCreationDate")),
    )


def _parse_seller(seller: Any) -> str | None:
    """Pull the seller's username out of eBay's seller object.

    Only the username. eBay also sends a feedback score and percentage, which
    would be a genuine signal when judging a copy, but nothing asks for them
    yet and an unused field is a field that goes stale without anyone
    noticing.
    """
    if not isinstance(seller, dict):
        return None
    return _optional_str(seller.get("username"))


def _parse_shipping(options: Any, index: int) -> Money | None:
    """Take the cheapest stated shipping cost, or `None` if none is stated.

    eBay returns several options — economy, expedited, sometimes local pickup
    — and the brief optimises for landed cost, so the cheapest is the one that
    decides whether a copy is worth buying. An option with no `shippingCost`
    usually means "calculated at checkout", which is not a number we can rank
    on and must not be read as free.
    """
    if not isinstance(options, list):
        return None

    costs = [
        _require_money(option["shippingCost"], "shippingCost", index)
        for option in options
        if isinstance(option, dict) and isinstance(option.get("shippingCost"), dict)
    ]
    if not costs:
        return None

    currencies = {cost.currency for cost in costs}
    if len(currencies) > 1:
        # Cheapest is meaningless across currencies, and picking one would be
        # arbitrary. Say nothing rather than something wrong.
        return None
    return min(costs, key=lambda cost: cost.amount)


def _parse_thumbnail(item: dict[str, Any]) -> str | None:
    image = item.get("image")
    if isinstance(image, dict):
        url = _optional_str(image.get("imageUrl"))
        if url:
            return url
    thumbnails = item.get("thumbnailImages")
    if isinstance(thumbnails, list):
        for thumbnail in thumbnails:
            if isinstance(thumbnail, dict):
                url = _optional_str(thumbnail.get("imageUrl"))
                if url:
                    return url
    return None


def _parse_date(raw: Any) -> datetime | None:
    """Parse eBay's ISO-8601 timestamps, tolerating their trailing `Z`."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        # A date we cannot read is worth less than the listing it is attached
        # to. Sorting by newness will simply not see this one.
        return None


def _require_str(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise EbaySearchError(
            f"Listing {index} had no usable {key}; keys present: {sorted(item)}"
        )
    return value


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _require_money(value: Any, label: str, index: int) -> Money:
    if not isinstance(value, dict):
        raise EbaySearchError(f"Listing {index} had no {label} object.")
    amount = value.get("value")
    currency = value.get("currency")
    if not isinstance(currency, str) or not currency:
        raise EbaySearchError(f"Listing {index} had a {label} with no currency.")
    try:
        # str() first: eBay sends these as strings, but a number would parse
        # through float otherwise and lose the exactness that is the point.
        return Money(Decimal(str(amount)), currency)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise EbaySearchError(
            f"Listing {index} had an unreadable {label} value: {amount!r}"
        ) from exc


def _decode_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise EbaySearchError(
            f"The eBay Browse API returned unreadable JSON: {_excerpt(response)}"
        ) from exc
    if not isinstance(payload, dict):
        raise EbaySearchError(
            f"Expected a JSON object from the eBay Browse API, got "
            f"{type(payload).__name__}"
        )
    return payload


def _describe_failure(response: httpx.Response) -> str:
    """Turn an error response into one line worth reading.

    Browse errors arrive as `{"errors": [{"errorId": .., "message": ..}]}`,
    and the message is usually specific enough to act on — a missing
    marketplace header and an exhausted call quota look nothing alike.
    """
    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                detail = " ".join(
                    str(part)
                    for part in (first.get("errorId"), first.get("message"))
                    if part
                )
    return (
        f"HTTP {response.status_code} from the eBay Browse API"
        f"{': ' + detail if detail else f' ({_excerpt(response)})'}"
    )


def _excerpt(response: httpx.Response, limit: int = 200) -> str:
    body = response.text.strip().replace("\n", " ")
    return body[:limit] + "…" if len(body) > limit else body


def main(argv: list[str] | None = None) -> int:
    """Print what eBay returns for a search term. One request."""
    args = list(sys.argv[1:] if argv is None else argv)
    search_by: SearchBy = "gtin" if "--gtin" in args else "keyword"
    terms = [arg for arg in args if not arg.startswith("--")]
    if not terms:
        print(
            "usage: python -m book_watch.ebay.search <search term> [--gtin]",
            file=sys.stderr,
        )
        return 2

    try:
        listings = search_listings(" ".join(terms), search_by=search_by)
    except MissingCredentialError as exc:
        print(f"Not configured: {exc}", file=sys.stderr)
        return 2
    except (EbayAuthError, EbaySearchError) as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1

    if not listings:
        print("No listings matched.")
        return 0

    print(f"{len(listings)} listing(s), searched by {search_by}:\n")
    for listing in listings:
        landed = listing.landed_cost
        cost = listing.shipping_cost
        shipping = "not stated" if cost is None else str(cost)
        print(listing.title)
        print(f"  condition  {listing.condition or 'unstated'}")
        print(f"  seller     {listing.seller or 'unstated'}")
        print(f"  price      {listing.price}")
        print(f"  shipping   {shipping}")
        print(f"  landed     {landed if landed is not None else 'unknown'}")
        print(f"  listed     {listing.listing_date or 'unstated'}")
        print(f"  image      {'yes' if listing.thumbnail_url else 'none'}")
        print(f"  {listing.item_web_url}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""What a seller declared about one listing.

eBay's search response carries a title, a price and a product id, and nothing
about the object itself. The ISBN, format, publisher and year come from a
second call per item — `getItem` — under `localizedAspects`.

Decision 33 measured that the declared ISBN is the strongest signal available
for deciding whether a listing is the book: 100% precision on the book
question, and the only thing that catches an omnibus. So the extra call earns
itself, and it is affordable because an item's aspects never change. One
request per listing, ever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from book_watch.ebay.auth import DEFAULT_TIMEOUT_SECONDS, USER_AGENT, EbayTokenProvider
from book_watch.ebay.errors import EbayAuthError, EbaySearchError
from book_watch.ebay.search import DEFAULT_MARKETPLACE_ID
from book_watch.isbn import normalise

ITEM_URL = "https://api.ebay.com/buy/browse/v1/item"

#: Aspect names that hold a number, in the order they are trusted. Sellers use
#: all of these, and `EAN` on a book is an ISBN-13 by definition.
_NUMBER_ASPECTS = ("ISBN-13", "ISBN", "EAN", "ISBN-10")

#: Sellers list several numbers in one field often enough to matter — a
#: hardcover and a paperback, or an ISBN-10 beside its ISBN-13.
_SEPARATORS = re.compile(r"[,;/|]|\bor\b")


@dataclass(frozen=True, slots=True)
class Declared:
    """What the seller said, as opposed to what is true.

    eBay prefills these from its own catalogue when a listing matched one, and
    lets the seller type them when it did not. That is why `format` holds
    "Trade Paperback" on one listing and "books" or "198x130x17 mm" on
    another, and why none of it is treated as fact.
    """

    item_id: str
    #: Whether eBay still has this listing. False means it has ended, sold or
    #: been withdrawn, and every other field on this object is empty because
    #: eBay said nothing — not because the seller did.
    #:
    #: The difference matters when re-asking about a listing we already know
    #: something about. A live seller who has cleared a field is telling us
    #: something; a 404 is not, and overwriting a good answer with its silence
    #: is how a record gets quietly lost.
    present: bool = True
    isbn: str | None = None
    #: Enough to rule a listing out, never enough to rule one in. A title is
    #: not a book: three different books called "Breaking and Entering" graded
    #: certain against each other until this was read.
    author: str | None = None
    format: str | None = None
    publisher: str | None = None
    published: str | None = None
    category: str | None = None


class ItemDetailClient:
    """Fetches one listing's aspects from eBay."""

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

    def declared_by(self, item_id: str) -> Declared:
        """Ask eBay what the seller said about this listing.

        An item that has gone — sold, ended, withdrawn — comes back as a
        `Declared` with nothing in it rather than an error. It was a real
        listing a moment ago and the fact that it is no longer buyable is not
        a failure of this call.
        """
        try:
            token = self._tokens.token()
        except EbayAuthError:
            raise
        # eBay's item ids contain pipes, which have to survive the path.
        url = f"{ITEM_URL}/{quote(item_id, safe='')}"
        try:
            response = self._client.get(url, headers=self._headers(token.value))
        except httpx.HTTPError as exc:
            raise EbaySearchError(f"Fetching {item_id} failed: {exc}") from exc

        if response.status_code == 404:
            return Declared(item_id=item_id, present=False)
        if response.status_code >= 400:
            raise EbaySearchError(
                f"Fetching {item_id} returned {response.status_code}: "
                f"{response.text[:200]!r}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise EbaySearchError(
                f"Fetching {item_id} returned a body that is not JSON: "
                f"{response.text[:200]!r}"
            ) from exc
        return _declared(item_id, payload)

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ItemDetailClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _declared(item_id: str, payload: Any) -> Declared:
    if not isinstance(payload, dict):
        raise EbaySearchError(
            f"Item {item_id} was {type(payload).__name__}, not an object."
        )
    aspects = _aspects(payload.get("localizedAspects"))
    return Declared(
        item_id=item_id,
        present=not _has_ended(payload),
        isbn=declared_isbn(aspects),
        author=aspects.get("Author"),
        format=aspects.get("Format"),
        publisher=aspects.get("Publisher"),
        published=aspects.get("Publication Year"),
        category=_optional(payload.get("categoryPath", "").rsplit("|", 1)[-1])
        if isinstance(payload.get("categoryPath"), str)
        else None,
    )


def _aspects(raw: Any) -> dict[str, str]:
    if not isinstance(raw, list):
        return {}
    found: dict[str, str] = {}
    for aspect in raw:
        if not isinstance(aspect, dict):
            continue
        name, value = aspect.get("name"), aspect.get("value")
        if isinstance(name, str) and isinstance(value, str):
            found.setdefault(name.strip(), value.strip())
    return found


def declared_isbn(aspects: dict[str, str]) -> str | None:
    """The first parseable ISBN-13 among the number-bearing aspects.

    Sellers scatter numbers across several fields and sometimes put more than
    one in a field — an ISBN-10 beside its ISBN-13, or a hardcover's number
    beside a paperback's. Everything is normalized, so the same edition typed
    two ways lands on one number.
    """
    for name in _NUMBER_ASPECTS:
        value = aspects.get(name)
        if not value:
            continue
        for chunk in _SEPARATORS.split(value):
            found = normalise(chunk.strip())
            if found:
                return found
    return None


def _optional(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _has_ended(payload: dict[str, Any]) -> bool:
    """Whether a 200 response is describing a listing that is already over.

    404 is the case we have seen and the one the caller mostly relies on. This
    covers the other shape, because eBay is not required to be consistent
    about it and the cost of being wrong here is silently overwriting a good
    declaration with an ended listing's emptiness.

    Anything unparseable counts as still running: a malformed date is not
    evidence that a listing has ended.
    """
    raw = payload.get("itemEndDate")
    if not isinstance(raw, str):
        return False
    try:
        ended = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=UTC)
    return ended <= datetime.now(UTC)

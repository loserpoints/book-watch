"""Read one AbeBooks or Biblio page, the way the app would, and say what it holds.

    python -m book_watch.pages <url>

One request, no retry. A path the site's robots.txt asks robots to stay out of
is refused before anything is sent. This exists to check, from the Fly
machine, that a page answers and what it carries. See docs/rules/api-policies.md.
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urlsplit

import httpx

#: Services are entitled to know who is calling them. See CLAUDE.md.
USER_AGENT = (
    "book-watch/0.1 (personal book want-list tool; "
    "+https://github.com/loserpoints/book-watch)"
)

TIMEOUT_SECONDS = 20.0

#: Paths each site's robots.txt disallows for every robot, as read on
#: 2026-10-06. A page under one of these is never requested.
DISALLOWED: dict[str, tuple[str, ...]] = {
    "www.abebooks.com": (
        "/servlet/",
        "/abe/",
        "/abep/",
        "/cgi/",
        "/search/",
        "/collections/",
        "/checkout/",
        "/discovery/",
    ),
    "www.biblio.com": (
        "/abrowse.php",
        "/app/",
        "/b/",
        "/bgsearch.php",
        "/book_photos/",
        "/booksellers/",
        "/m/",
        "/o/",
        "/remote-search",
        "/search.php",
        "/w/",
        "/wants.php",
        "/z/",
    ),
}

_COUNT = re.compile(r'data-test-id="result-count"[^>]*>\s*\(([\d,]+) results?\)')
_LISTING = re.compile(r'data-srp-item-role="listing"')
_LISTING_ID = re.compile(r'data-csa-c-item-id="(\d+)"')
_PRICE = re.compile(r"US\$\s?([\d,]+\.\d{2})")
_SHIPPING = re.compile(r"US\$\s?([\d,]+\.\d{2}) shipping")
_FIRST_EDITION = re.compile(r"\bFirst Edition\b")


class RefusedPath(ValueError):
    """The page is on a site this module doesn't read, or robots.txt disallows it."""


@dataclass(frozen=True, slots=True)
class Copy:
    listing_id: str | None
    price: Decimal | None
    #: Zero for free shipping. None when the page states no shipping at all.
    shipping: Decimal | None
    first_edition: bool

    @property
    def delivered(self) -> Decimal | None:
        if self.price is None or self.shipping is None:
            return None
        return self.price + self.shipping


@dataclass(frozen=True, slots=True)
class Page:
    #: The page's own count of results, which may be more than it shows.
    result_count: int | None
    copies: list[Copy] = field(default_factory=list)
    #: True when the site answered with a bot challenge instead of the page.
    challenged: bool = False


def check_url(url: str) -> None:
    """Refuse a page this module must not request."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc not in DISALLOWED:
        raise RefusedPath(f"not an AbeBooks or Biblio page: {url}")
    path = parts.path or "/"
    for prefix in DISALLOWED[parts.netloc]:
        if path.startswith(prefix):
            raise RefusedPath(f"robots.txt disallows {prefix} on {parts.netloc}")


def _text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style).*?</\1>", " ", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def parse(page: str) -> Page:
    """What a search or ISBN page holds: its count and each copy on it."""
    if "<title>Just a moment...</title>" in page:
        return Page(result_count=None, challenged=True)

    count = _COUNT.search(page)
    starts = [m.start() for m in _LISTING.finditer(page)]
    copies = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(page)
        block = page[start:end]
        listing_id = _LISTING_ID.search(page[max(0, start - 600) : start + 600])
        text = _text(block)
        price = _PRICE.search(text)
        shipping = _SHIPPING.search(text)
        if shipping:
            cost: Decimal | None = _money(shipping.group(1))
        elif "Free Shipping" in text or "Free shipping" in text:
            cost = Decimal("0")
        else:
            cost = None
        copies.append(
            Copy(
                listing_id=listing_id.group(1) if listing_id else None,
                price=_money(price.group(1)) if price else None,
                shipping=cost,
                first_edition=bool(_FIRST_EDITION.search(text)),
            )
        )
    return Page(
        result_count=int(count.group(1).replace(",", "")) if count else None,
        copies=copies,
    )


def fetch(url: str) -> tuple[int, str]:
    """One request, no retry. Returns the status and the body."""
    check_url(url)
    response = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    return response.status_code, response.text


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m book_watch.pages <url>", file=sys.stderr)
        return 2
    try:
        status, body = fetch(args[0])
    except RefusedPath as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    page = parse(body)
    print(f"status     {status}")
    print(f"bytes      {len(body)}")
    if page.challenged:
        print("challenge  the site answered with a bot challenge, not the page")
        return 1
    print(f"results    {page.result_count if page.result_count is not None else '?'}")
    print(f"on page    {len(page.copies)}")
    delivered = [c.delivered for c in page.copies if c.delivered is not None]
    print(f"cheapest   {', '.join(str(d) for d in delivered[:10]) or 'none'}")
    print(f"in order   {'yes' if delivered == sorted(delivered) else 'no'}")
    print(f"first ed.  {sum(c.first_edition for c in page.copies)}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())

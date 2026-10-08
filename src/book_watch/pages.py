"""Read one AbeBooks or Biblio page, the way the app would, and say what it holds.

    python -m book_watch.pages <url> [--markup] [--ungrouped]

One request, no retry. `--markup` also prints the page itself, without its
scripts, styles, icons and comments, to see a page that holds no copies.
`--ungrouped` asks for the page without grouped rows.
A path the site's robots.txt asks robots to stay out of is refused before
anything is sent. This exists to check, from the Fly machine, that a page
answers and what it carries. See docs/rules/api-policies.md.
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from book_watch import monitoring

#: Services are entitled to know who is calling them. See CLAUDE.md.
USER_AGENT = (
    "book-watch/0.1 (personal book want-list tool; "
    "+https://github.com/loserpoints/book-watch)"
)

TIMEOUT_SECONDS = 20.0

#: AbeBooks' own setting for a search page without grouped rows, carried by
#: every link on its search pages. Grouping came and went on 2026-10-07 (S76).
UNGROUPED = "rollup=off"

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

#: "(71 results)", or "(Over 1,500 results)" for large ones.
_COUNT = re.compile(
    r'data-test-id="result-count"[^>]*>\s*\((?:Over )?([\d,]+) results?\)'
)
_LISTING = re.compile(r'data-srp-item-role="listing"')
_LISTING_ID = re.compile(r'data-csa-c-item-id="(\d+)"')
_PRICE = re.compile(r"US\$\s?([\d,]+\.\d{2})")
_SHIPPING = re.compile(r"US\$\s?([\d,]+\.\d{2}) shipping")
_FIRST_EDITION = re.compile(r"\bFirst Edition\b")
#: "ISBN 10 / ISBN 13: 0670337285 / 9780670337286" or "ISBN 13: 9780670337286".
_ISBN13 = re.compile(r"ISBN (?:10 / ISBN )?13: (?:[\dX]{10} / )?(97[89]\d{10})")
#: AbeBooks' own page for a search with nothing on it, title or ISBN alike.
#: Matched only in what the page shows: every results page also carries the
#: sentence in its scripts, as *Hey Jack!*'s did on 2026-10-08.
_NO_RESULTS = re.compile(r"We were unable to find exact matches based on your search")
_GROUPED = re.compile(r"(?:Used|New) offers from US\$")
_PHOTO = re.compile(r'<img\b[^>]*\bsrc="(https://pictures\.abebooks\.com/[^"]+)"')
#: "Published by The Viking Press, New York, 1972": the publisher, then the year.
_PUBLISHED = re.compile(r"^Published by (.+?)(?:, (\d{4}))?$")
_BINDING = re.compile(
    r"\b(Hardcover|Softcover|Paperback|Mass Market Paperback|Leather Bound|"
    r"Hard cover|Soft cover)\b"
)
_ORIGIN = "https://www.abebooks.com"
#: What `--markup` leaves out: code, styling, icons and comments.
_NOT_MARKUP = re.compile(
    r"<(script|style|svg|noscript)\b.*?</\1\s*>|<!--.*?-->", re.DOTALL | re.IGNORECASE
)
#: Elements that never close, so they never open a level.
_VOID = {"img", "br", "input", "meta", "link", "hr", "source", "wbr", "area"}


class RefusedPath(ValueError):
    """The page is on a site this module doesn't read, or robots.txt disallows it."""


@dataclass(frozen=True, slots=True)
class Copy:
    listing_id: str | None
    price: Decimal | None
    #: Zero for free shipping. None when the page states no shipping at all.
    shipping: Decimal | None
    first_edition: bool
    #: None when the seller entered no ISBN.
    isbn: str | None = None
    #: A row that stands for every copy of its edition, priced at the cheapest.
    grouped: bool = False
    title: str | None = None
    #: The listing's page on the marketplace, absolute.
    url: str | None = None
    author: str | None = None
    publisher: str | None = None
    published: str | None = None
    binding: str | None = None
    #: The marketplace's own words, such as "Used - Very good".
    condition: str | None = None
    seller: str | None = None
    #: Where the seller is, as the page writes it: "Silver Spring, MD, U.S.A.".
    location: str | None = None
    photo: str | None = None
    #: The seller's description of the copy.
    note: str | None = None

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
    #: True when the page says the search found nothing.
    no_results: bool = False


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


class _Fields(HTMLParser):
    """The text and attributes of each element a listing marks with a test id."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self._open: list[tuple[str, int]] = []
        self.text: dict[str, list[str]] = {}
        self.attrs: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = dict(attrs)
        test_id = named.get("data-test-id")
        if test_id and test_id not in self.attrs:
            self.attrs[test_id] = named
            self.text[test_id] = []
        if tag in _VOID:
            return
        self._depth += 1
        if test_id:
            self._open.append((test_id, self._depth))

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        self._open = [
            (name, depth) for name, depth in self._open if depth < self._depth
        ]
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        for name, _ in self._open:
            self.text[name].append(data)

    def get(self, name: str) -> str | None:
        """The text of the element with this test id, or with it numbered.

        Some ids carry the row's number, such as "description-2"; a different
        id that merely starts the same way, such as "listing-condition-label",
        is not this one.
        """
        numbered = re.compile(rf"{re.escape(name)}(?:-\d+)?$")
        for found in (name, *self.text):
            if found in self.text and numbered.match(found):
                value = re.sub(r"\s+", " ", "".join(self.text[found])).strip()
                return value or None
        return None

    def link(self, name: str) -> str | None:
        href = self.attrs.get(name, {}).get("href")
        return urljoin(_ORIGIN, html.unescape(href)) if href else None

    def has(self, prefix: str) -> bool:
        return any(name.startswith(prefix) for name in self.attrs)


def _location(seller_info: str | None, seller: str | None) -> str | None:
    """The location from "Seller: Type Punch Matrix, Silver Spring, MD, U.S.A."."""
    if not seller_info:
        return None
    text = seller_info.removeprefix("Seller:").strip()
    if seller and text.startswith(seller):
        text = text[len(seller) :].lstrip(", ")
    # The page repeats the line; the first copy of it is enough.
    if seller and seller in text:
        text = text[: text.index(seller)].rstrip(", ")
    return text or None


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
        fields = _Fields()
        fields.feed(block)
        seller = fields.get("listing-seller-link")
        published = _PUBLISHED.match(fields.get("publisher") or "")
        binding = _BINDING.search(fields.get("listing-item") or text)
        photo = _PHOTO.search(block)
        copies.append(
            Copy(
                listing_id=listing_id.group(1) if listing_id else None,
                price=_money(price.group(1)) if price else None,
                shipping=cost,
                first_edition=bool(_FIRST_EDITION.search(text)),
                isbn=isbn.group(1) if (isbn := _ISBN13.search(text)) else None,
                grouped=bool(_GROUPED.search(text)) or fields.has("listing-rollup"),
                title=fields.get("listing-title"),
                url=fields.link("listing-title-link"),
                author=fields.get("listing-author"),
                publisher=published.group(1) if published else None,
                published=published.group(2) if published else None,
                binding=binding.group(1) if binding else None,
                condition=fields.get("listing-condition"),
                seller=seller,
                location=_location(fields.get("seller-info"), seller),
                photo=photo.group(1) if photo else None,
                note=fields.get("description"),
            )
        )
    return Page(
        result_count=int(count.group(1).replace(",", "")) if count else None,
        copies=copies,
        no_results=bool(_NO_RESULTS.search(markup(page))),
    )


def ungrouped(url: str) -> str:
    """The address, asking for no grouped rows."""
    return f"{url}{'&' if '?' in url else '?'}{UNGROUPED}"


def markup(page: str) -> str:
    """The page without what `_NOT_MARKUP` names, and without blank lines."""
    lines = (line.strip() for line in _NOT_MARKUP.sub("", page).splitlines())
    return "\n".join(line for line in lines if line)


def fetch(url: str, transport: httpx.BaseTransport | None = None) -> tuple[int, str]:
    """One request, no retry. Returns the status and the body.

    A redirect is followed only to a page `check_url` allows: every hop is
    checked before it is sent, not only the address asked for.
    """
    check_url(url)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        event_hooks={"request": [lambda request: check_url(str(request.url))]},
        transport=transport,
    ) as client:
        response = client.get(url)
    return response.status_code, response.text


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    flags = {arg for arg in args if arg.startswith("--")}
    args = [arg for arg in args if not arg.startswith("--")]
    if len(args) != 1 or flags - {"--markup", "--ungrouped"}:
        print(
            "usage: python -m book_watch.pages <url> [--markup] [--ungrouped]",
            file=sys.stderr,
        )
        return 2
    url = ungrouped(args[0]) if "--ungrouped" in flags else args[0]
    try:
        status, body = fetch(url)
    except RefusedPath as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    page = parse(body)
    print(f"address    {url}")
    print(f"status     {status}")
    print(f"bytes      {len(body)}")
    if page.challenged:
        print("challenge  the site answered with a bot challenge, not the page")
        return 1
    print(f"results    {page.result_count if page.result_count is not None else '?'}")
    print(f"on page    {len(page.copies)}")
    print(f"no results {'yes' if page.no_results else 'no'}")
    delivered = [c.delivered for c in page.copies if c.delivered is not None]
    print(f"cheapest   {', '.join(str(d) for d in delivered[:10]) or 'none'}")
    print(f"in order   {'yes' if delivered == sorted(delivered) else 'no'}")
    print(f"first ed.  {sum(c.first_edition for c in page.copies)}")
    isbns = sorted({c.isbn for c in page.copies if c.isbn})
    print(f"isbns      {len(isbns)}: {', '.join(isbns) or 'none'}")
    print(f"no isbn    {sum(c.isbn is None for c in page.copies)}")
    for copy in page.copies:
        print(
            f"  {copy.isbn or '-':13}  {str(copy.delivered or '?'):>8}"
            f"  {'grouped' if copy.grouped else '       '}"
            f"  {'first ed.' if copy.first_edition else ''}"
        )
    if "--markup" in flags:
        print("markup")
        print(markup(body))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    # Run from a GitHub workflow, so its calls say so.
    with monitoring.started_by("test"):
        raise SystemExit(main())

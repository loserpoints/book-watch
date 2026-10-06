"""Read a book's copies from AbeBooks, one request per book (S66, #229).

The page read is page 1 of AbeBooks' title search, which AbeBooks serves to
the Fly machine as one row per copy, cheapest first by delivered price: the
book's 30 cheapest copies across its editions. Nothing past page 1 and no path
robots.txt disallows is ever requested. See docs/rules/api-policies.md.

A page the app cannot read correctly fails the check rather than being
guessed at: the book's page says the check failed, the log says why, and
eBay's copies are untouched. Price order is measured rather than required:
real pages are only roughly cheapest first, and the daily check counts the
pages that are not.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import httpx

from book_watch import pages, sweeps, wantlist
from book_watch.ebay.search import Listing, Money, Results
from book_watch.isbn import normalize
from book_watch.marketplaces import abebooks_condition_id

logger = logging.getLogger(__name__)

SEARCH = "https://www.abebooks.com/book-search/title/{title}/author/{author}/"
ISBN_PAGE = "https://www.abebooks.com/book-search/isbn/{isbn}/used/"

#: Rows on a page. Nothing past the first page is read.
PAGE_SIZE = 30

#: The least time between two requests to AbeBooks, from anywhere in the app.
SPACING_SECONDS = 3.0

#: How much cheaper than a copy above it a copy must be to count as out of
#: place. Rounding moves neighbors by cents, which says nothing.
ORDER_SLACK = Decimal("1.00")

#: More copies out of place than this, and the page is out of order: no
#: longer the cheapest-first page S64 found.
OUT_OF_PLACE_ALLOWED = 3

#: A country as AbeBooks writes it at the end of a seller's location, as the
#: two-letter code eBay uses. A country not here is left unknown, which shows
#: the copy under Everywhere and never under US-only.
_COUNTRIES = {
    "U.S.A.": "US",
    "United Kingdom": "GB",
    "Canada": "CA",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Ireland": "IE",
    "Australia": "AU",
    "New Zealand": "NZ",
    "Netherlands": "NL",
    "India": "IN",
}

#: Reads a page and answers what it holds, or raises.
Reader = Callable[[str], pages.Page]


class AbeBooksError(Exception):
    """AbeBooks answered with something other than a page S64 has seen."""


def slug(text: str) -> str:
    """Words as AbeBooks reads them in a path: lowercase, no punctuation,
    joined by hyphens. Accents are dropped to their letters."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9\s]", "", plain.lower()).split()
    return "-".join(words)


def search_url(title: str | None, author: str | None, typed: str | None) -> str | None:
    """The page to read for a book, or None when there is nothing to search.

    The main title only, before any colon: a subtitle narrows the search,
    since many sellers leave it out. A book with no title but a typed ISBN is
    read from that ISBN's page.
    """
    if title:
        main = slug(title.split(":", 1)[0])
        if main:
            return SEARCH.format(title=main, author=slug(author or "") or "_")
    isbn = normalize(typed) if typed else None
    if isbn:
        return ISBN_PAGE.format(isbn=isbn)
    return None


_lock = threading.Lock()
_last_request: float | None = None


def read(url: str) -> pages.Page:
    """Read one page, spaced from every other request, and check its shape."""
    global _last_request
    with _lock:
        if _last_request is not None:
            wait = SPACING_SECONDS - (time.monotonic() - _last_request)
            if wait > 0:
                time.sleep(wait)
        try:
            status, body = pages.fetch(url)
        finally:
            _last_request = time.monotonic()
    if status != 200:
        raise AbeBooksError(f"status {status}")
    return checked(pages.parse(body))


def checked(page: pages.Page) -> pages.Page:
    """The page, if it is in the shape S64 found; otherwise why not."""
    if page.challenged:
        raise AbeBooksError("bot challenge")
    if not page.copies:
        return page  # An ordinary empty result.
    if page.result_count is None:
        raise AbeBooksError("copies without a count")
    if any(copy.grouped for copy in page.copies):
        raise AbeBooksError("grouped rows")
    delivered = [copy.delivered for copy in page.copies]
    if any(price is None for price in delivered) or any(
        not copy.listing_id or not copy.url for copy in page.copies
    ):
        raise AbeBooksError("a copy without a price, an id or a link")
    return page


def out_of_place(page: pages.Page) -> int:
    """How many copies are more than `ORDER_SLACK` cheaper than one above.

    Measured, never enforced: a real page has a straggler or two, such as a
    foreign seller sorted at a different price than it shows.
    """
    dearest: Decimal | None = None
    count = 0
    for copy in page.copies:
        price = copy.delivered
        if price is None:
            continue
        if dearest is not None and price < dearest - ORDER_SLACK:
            count += 1
        dearest = price if dearest is None else max(dearest, price)
    return count


@dataclass(frozen=True, slots=True)
class Result:
    """How one book's check went."""

    #: "ok", "empty" or "failed".
    outcome: str
    out_of_place: int = 0

    @property
    def unordered(self) -> bool:
        return self.out_of_place > OUT_OF_PLACE_ALLOWED


def country(location: str | None) -> str | None:
    """The two-letter code for a seller's location, or None when unknown."""
    if not location:
        return None
    return _COUNTRIES.get(location.rsplit(",", 1)[-1].strip())


def _listing(copy: pages.Copy) -> Listing:
    assert copy.listing_id and copy.url and copy.price is not None
    return Listing(
        item_id=copy.listing_id,
        title=copy.title or "",
        price=Money(copy.price, "USD"),
        item_web_url=copy.url,
        located_in=country(copy.location),
        condition=copy.condition,
        condition_id=abebooks_condition_id(copy.condition),
        seller=copy.seller,
        shipping_cost=Money(copy.shipping, "USD")
        if copy.shipping is not None
        else None,
        thumbnail_url=copy.photo,
    )


def _declare(connection: sqlite3.Connection, copy: pages.Copy) -> None:
    """What the page says about the copy, stored as eBay's declarations are."""
    connection.execute(
        """
        INSERT INTO listing_declaration (
            marketplace, item_id, isbn, author, format, publisher, published,
            condition_note, photos
        ) VALUES ('abebooks', ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (marketplace, item_id) DO UPDATE SET
            isbn = excluded.isbn,
            author = excluded.author,
            format = excluded.format,
            publisher = excluded.publisher,
            published = excluded.published,
            condition_note = excluded.condition_note,
            photos = excluded.photos,
            fetched_at = datetime('now')
        """,
        (
            copy.listing_id,
            copy.isbn,
            copy.author,
            copy.binding,
            copy.publisher,
            copy.published,
            copy.note,
            json.dumps([copy.photo]) if copy.photo else None,
        ),
    )


def _record(
    connection: sqlite3.Connection, work_id: int, outcome: str, reason: str | None
) -> None:
    connection.execute(
        "INSERT INTO marketplace_check (work_id, marketplace, outcome, reason) "
        "VALUES (?, 'abebooks', ?, ?) "
        "ON CONFLICT (work_id, marketplace) DO UPDATE SET "
        "checked_at = datetime('now'), outcome = excluded.outcome, "
        "reason = excluded.reason",
        (work_id, outcome, reason),
    )


def check(
    connection: sqlite3.Connection,
    work_id: int,
    url: str | None,
    reader: Reader,
) -> Result:
    """Read one book's AbeBooks page and store what it holds.

    A failure stores no sweep, so the copies from the last good check stay
    listed as of then. Commits.
    """
    if url is None:
        return Result("empty")
    try:
        page = reader(url)
    except (AbeBooksError, httpx.HTTPError, pages.RefusedPath) as exc:
        logger.warning("AbeBooks check failed for work %s: %s", work_id, exc)
        _record(connection, work_id, "failed", str(exc))
        connection.commit()
        return Result("failed")

    result = Result("ok" if page.copies else "empty", out_of_place(page))
    if result.unordered:
        logger.warning(
            "AbeBooks page out of order for work %s: %d of %d copies out of place",
            work_id,
            result.out_of_place,
            len(page.copies),
        )

    listings = Results(
        [_listing(copy) for copy in page.copies], total=page.result_count or 0
    )
    sweeps.store_both_scopes(
        connection, work_id, listings, asked_for=PAGE_SIZE, marketplace="abebooks"
    )
    for copy in page.copies:
        _declare(connection, copy)
    _record(connection, work_id, result.outcome, None)
    connection.commit()
    return result


def last_outcome(connection: sqlite3.Connection, work_id: int) -> str | None:
    """How this book's last AbeBooks check went, or None if never checked."""
    row = connection.execute(
        "SELECT outcome FROM marketplace_check "
        "WHERE work_id = ? AND marketplace = 'abebooks'",
        (work_id,),
    ).fetchone()
    return row["outcome"] if row else None


def due(connection: sqlite3.Connection, work_id: int) -> bool:
    """Whether this book's AbeBooks page should be read again.

    The same hour as eBay's gate, counted from the last check whatever its
    outcome: a page that failed is not read again on every visit.
    """
    row = connection.execute(
        "SELECT checked_at FROM marketplace_check "
        "WHERE work_id = ? AND marketplace = 'abebooks' "
        "AND checked_at > datetime('now', ?)",
        (work_id, f"-{int(sweeps.CURRENT_FOR.total_seconds())} seconds"),
    ).fetchone()
    return row is None


def check_book(
    connection: sqlite3.Connection,
    book: wantlist.Entry,
    reader: Reader | None,
    *,
    force: bool = False,
) -> Result | None:
    """Check one want-list book, if a reader is set and the gate allows.

    Returns how it went, or None when nothing was read. Called right after
    eBay's search and before new copies are examined, so a book says
    "digging" until both marketplaces' copies have been looked at.
    """
    if reader is None or not (force or due(connection, book.work_id)):
        return None
    url = search_url(book.title, book.author, book.typed)
    return check(connection, book.work_id, url, reader)

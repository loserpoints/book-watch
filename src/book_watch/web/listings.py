"""The results pages: eBay listings for an ISBN, or for a book on the list.

Searches eBay when the page loads. That is a placeholder, not the design —
it is fine at one user's handful of page views a day against a 5,000-call
budget, and the cache that replaces it arrives with the daily poll. If this
is still here once anything polls on a schedule, something has gone wrong.

The search function is injected so the whole page can be tested without a
network, a key, or eBay being up.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch import wantlist
from book_watch.config import MissingCredentialError, load_ebay_credentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import DEFAULT_LIMIT, MAX_LIMIT, BrowseClient, Listing
from book_watch.isbn import normalise
from book_watch.web.wantlist import ConnectFn, open_configured_database

SEARCH_PATH = "/search"
BOOK_PATH = "/book/{book_id}"

TEMPLATES_DIR = Path(__file__).parent / "templates"

#: Takes a query and a limit, returns listings. `BrowseClient.search` is the
#: real one; tests pass a function that returns whatever they need.
SearchFn = Callable[[str, int], list[Listing]]


class LazyBrowseSearch:
    """Builds the eBay client on first search rather than at startup.

    This laziness is load-bearing, not tidiness. Fly holds the deletion
    endpoint's secrets and *not* the eBay keys, so an application that read
    `EBAY_CLIENT_ID` while booting would fail to start in production. That
    endpoint carries an uptime obligation which has nothing to do with the
    rest of the app — eBay re-validates it on its own schedule and disables
    the keyset when the check fails (decisions.md entry 16).

    So a missing key breaks searching, loudly, and breaks nothing else.
    """

    def __init__(self) -> None:
        self._browse: BrowseClient | None = None

    def __call__(self, query: str, limit: int) -> list[Listing]:
        if self._browse is None:
            tokens = EbayTokenProvider(load_ebay_credentials())
            self._browse = BrowseClient(tokens)
        return self._browse.search(query, limit=limit)


def build_router(
    search: SearchFn | None = None, connect: ConnectFn | None = None
) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )

    def search_and_render(
        request: Request,
        query: str,
        limit: int,
        *,
        book: wantlist.Entry | None = None,
    ) -> HTMLResponse:
        """Run one search and render it, or render why it could not run."""
        context: dict[str, object] = {
            "isbn": query,
            "book": book,
            "listings": [],
            "error": None,
            # Stated rather than implied. Every listing on this page was
            # fetched for this request; when the daily poll replaces that,
            # this line is where "last checked on Tuesday" has to go, and a
            # page with nowhere to say so is a page that quietly lies.
            "fetched_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            # An overridden entry is not an ISBN, so eBay gets a keyword
            # search for whatever was typed. Say so; "nothing listed" would
            # otherwise look like a fact about the market.
            "is_isbn": normalise(query) is not None,
        }

        # These two status codes are a contract, not decoration: the deploy
        # workflow's search smoke check reads them to tell a missing key from
        # a rejected one. Changing either to 200 would make a broken deploy
        # look green.
        try:
            context["listings"] = run_search(query, limit)
        except MissingCredentialError as exc:
            context["error"] = f"eBay is not configured: {exc}"
            return templates.TemplateResponse(
                request, "search.html", context, status_code=500
            )
        except EbayError as exc:
            context["error"] = f"eBay could not be searched: {exc}"
            return templates.TemplateResponse(
                request, "search.html", context, status_code=502
            )

        return templates.TemplateResponse(request, "search.html", context)

    @router.get(SEARCH_PATH, response_class=HTMLResponse)
    def results(
        request: Request,
        isbn: str = "",
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    ) -> HTMLResponse:
        query = isbn.strip()
        if not query:
            # Not an error: an empty box is what you get before you ask for
            # anything. The page explains itself instead of complaining.
            return templates.TemplateResponse(
                request,
                "search.html",
                {"isbn": "", "book": None, "listings": [], "error": None},
            )
        # Keyword, not GTIN — decisions.md entry 21. Sellers put the ISBN in
        # the title and leave eBay's structured fields empty.
        return search_and_render(request, query, limit)

    @router.get(BOOK_PATH, response_class=HTMLResponse)
    def book_results(
        request: Request,
        book_id: int,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    ) -> HTMLResponse:
        """What is for sale, right now, for one book on the want-list."""
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                return templates.TemplateResponse(
                    request,
                    "search.html",
                    {
                        "isbn": "",
                        "book": None,
                        "listings": [],
                        "error": "That book is not on the want-list.",
                    },
                    status_code=404,
                )

        return search_and_render(request, book.search_query, limit, book=book)

    return router

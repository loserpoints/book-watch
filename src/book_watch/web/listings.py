"""The results page: eBay listings for one ISBN, rendered server-side.

Searches eBay when the page loads. That is a placeholder, not the design —
it is fine at one user's handful of page views a day against a 5,000-call
budget, and the cache that replaces it arrives with the daily poll. If this
is still here once anything polls on a schedule, something has gone wrong.

The search function is injected so the whole page can be tested without a
network, a key, or eBay being up.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch.config import MissingCredentialError, load_ebay_credentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import DEFAULT_LIMIT, MAX_LIMIT, BrowseClient, Listing

SEARCH_PATH = "/search"

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


def build_router(search: SearchFn | None = None) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()

    @router.get(SEARCH_PATH, response_class=HTMLResponse)
    def results(
        request: Request,
        isbn: str = "",
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    ) -> HTMLResponse:
        query = isbn.strip()
        context: dict[str, object] = {"isbn": query, "listings": [], "error": None}

        if not query:
            # Not an error: an empty box is what you get before you ask for
            # anything. The page explains itself instead of complaining.
            return templates.TemplateResponse(request, "search.html", context)

        try:
            # Keyword, not GTIN — decisions.md entry 21. Sellers put the ISBN
            # in the title and leave eBay's structured fields empty.
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

    return router

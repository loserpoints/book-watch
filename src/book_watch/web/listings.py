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

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch import copies, enrichment, wantlist
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

#: Start a background pass over one book's copies. Injected, like everything
#: else that reaches a third party, so a test cannot reach one by omission.
EnrichFn = Callable[[int], object]


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


def _configured_enrichment(connect: ConnectFn) -> EnrichFn:
    """Wire an enrichment pass to real eBay and real Open Library.

    Built lazily for the same reason everything else here is: nothing that
    could fail for want of a credential may run while the compliance endpoint
    is trying to boot (decision 24).
    """

    def start(work_id: int) -> object:
        from book_watch.ebay.declarations import Declarations
        from book_watch.ebay.detail import ItemDetailClient
        from book_watch.openlibrary import CallBudget, OpenLibraryClient, Resolver

        detail = ItemDetailClient(EbayTokenProvider(load_ebay_credentials()))
        catalogue = OpenLibraryClient(CallBudget(connect))
        return enrichment.enrich(
            connect,
            work_id,
            lambda connection: Declarations(connection, detail),
            lambda connection: Resolver(connection, catalogue),
        )

    return start


def build_router(
    search: SearchFn | None = None,
    connect: ConnectFn | None = None,
    enrich: EnrichFn | None = None,
) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    templates.env.filters["ago"] = _ago
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )
    start_enrichment: EnrichFn = (
        enrich if enrich is not None else _configured_enrichment(open_database)
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
        background: BackgroundTasks,
        book_id: int,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        refresh: int = 0,
    ) -> HTMLResponse:
        """What is for sale for one book, graded by how sure we are.

        The page reads the store. It searches eBay only when this book has
        never been searched for, or when asked to refresh — decision 30 as
        amended. It never fetches a listing's detail: measured at 0.51s each,
        fifty of them is twenty-five seconds, and that work belongs to the
        background.
        """
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

            error = None
            # Opening a book is a request to see what is listed *now* — there
            # is no other reason to click a book's title. It used to search
            # only on a book's first-ever view, so the page showed copies that
            # may have sold days earlier and hid copies listed since. Decision
            # 40, amended.
            if refresh or copies.due_for_sweep(connection, book.work_id):
                try:
                    copies.store(
                        connection,
                        book.work_id,
                        run_search(book.search_query, limit),
                        asked_for=limit,
                    )
                    connection.commit()
                    book = wantlist.get(connection, book_id)
                except MissingCredentialError as exc:
                    error = (f"eBay is not configured: {exc}", 500)
                except EbayError as exc:
                    error = (f"eBay could not be searched: {exc}", 502)

            for_sale = copies.for_entry(connection, book)
            checked = copies.swept_at(connection, book.work_id)

        # Scheduled after the response is written, never before it. Decision
        # 40: examining fifty copies is twenty-five seconds of eBay, and this
        # page owes an answer in two.
        #
        # The condition is "has a pass finished", not "is there a copy eBay
        # has never been asked about". The second was the original and it was
        # wrong in a way nothing caught: after the first pass there is never
        # an unasked copy, so enrichment ran once per book and never again —
        # and every later fix to what a pass does was dead code in production
        # while passing every test, because tests start from an empty
        # database and production does not.
        if book.enriched_at is None:
            background.add_task(start_enrichment, book.work_id)

        shown = [copy for copy in for_sale if copy.tier != "excluded"]
        context = {
            "isbn": book.search_query,
            "book": book,
            "copies": [copy for copy in shown if copy.tier == "certain"],
            "uncertain": [copy for copy in shown if copy.tier != "certain"],
            "hidden": len(for_sale) - len(shown),
            "unlooked": len(copies.unasked(for_sale)),
            "listings": [],
            "error": error[0] if error else None,
            "fetched_at": book.copies_fetched_at or "never",
            "checked": checked,
            "is_isbn": normalise(book.search_query) is not None,
        }
        return templates.TemplateResponse(
            request, "book.html", context, status_code=error[1] if error else 200
        )

    return router


def _ago(when: datetime | None) -> str:
    """How long ago, in words a person reads at a glance.

    "checked 2026-09-23 20:48:08" tells you nothing without arithmetic, which
    is the point of issue #22. This is the part of it this slice needs: the
    page's whole claim is about how current its results are, so the one number
    that matters must not need working out.
    """
    if when is None:
        return "never"
    seconds = (datetime.now(UTC) - when).total_seconds()
    if seconds < 90:
        return "just now"
    for size, unit in ((60, "minute"), (3600, "hour"), (86400, "day")):
        count = int(seconds // size)
        if count < _size_of_next(unit):
            return f"{count} {unit}{'' if count == 1 else 's'} ago"
    weeks = max(1, int(seconds // 604800))
    return f"{weeks} week{'' if weeks == 1 else 's'} ago"


def _size_of_next(unit: str) -> int:
    """How many of `unit` fit before the next unit up takes over."""
    return {"minute": 60, "hour": 24, "day": 14}[unit]

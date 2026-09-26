"""One book: what is for sale, what it costs, and the most I will pay.

**Opening a book searches eBay, and that is the design rather than a
placeholder** — an earlier version of this docstring called it one. There is
no other reason to click a book's title than to find out what is listed
*now*, and the version that searched only on a book's first-ever view showed
copies that may have sold days earlier (decision 48). A sweep is gated to one
an hour per scope so the list holds still long enough to act on, and a button
ignores the gate on demand.

It never fetches a listing's details: measured at 0.51s each, fifty of them
is twenty-five seconds, and that work belongs to the background pass.

The ad-hoc `/search` page shares this module because it asks the same
question of eBay without a book on the list behind it. The want-list and its
checking live in `wantlist`; the search wiring both need is in `searching`.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from book_watch import copies, enrichment, standing, sweeps, wantlist
from book_watch.config import MissingCredentialError, load_ebay_credentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Scope,
)
from book_watch.isbn import normalise
from book_watch.web import assets, filters
from book_watch.web.searching import LazyBrowseSearch, SearchFn
from book_watch.web.wantlist import ConnectFn, open_configured_database

SEARCH_PATH = "/search"
BOOK_PATH = "/book/{book_id}"
CEILING_PATH = "/book/{book_id}/ceiling"

TEMPLATES_DIR = Path(__file__).parent / "templates"


#: Start a background pass over one book's copies. Injected, like everything
#: else that reaches a third party, so a test cannot reach one by omission.
EnrichFn = Callable[[int], object]


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
    filters.register(templates.env)
    assets.register(templates.env)
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
        everywhere: int = 0,
    ) -> HTMLResponse:
        """What is for sale for one book, graded by how sure we are.

        The page reads the store. It searches eBay only when this book has
        never been searched for, or when asked to refresh — decision 48,
        which amended decision 40. It never fetches a listing's detail:
        measured at 0.51s each, fifty of them is twenty-five seconds, and
        that work belongs to the background.
        """
        # Nothing is persisted. A toggle that quietly changed what every later
        # visit searched for would be a setting wearing a link's clothes, and
        # settings are #72.
        scope: Scope = "everywhere" if everywhere else "us"
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
            # The gate is per scope. A recent US sweep must not block a
            # first look at everything: they are different questions, and an
            # everywhere sweep finds fewer US copies because imports displace
            # them out of the fifty slots.
            if refresh or sweeps.due_for_sweep(connection, book.work_id, scope=scope):
                try:
                    sweeps.store(
                        connection,
                        book.work_id,
                        run_search(book.search_query, limit, scope=scope),
                        asked_for=limit,
                        scope=scope,
                    )
                    connection.commit()
                    book = wantlist.get(connection, book_id)
                except MissingCredentialError as exc:
                    error = (f"eBay is not configured: {exc}", 500)
                except EbayError as exc:
                    error = (f"eBay could not be searched: {exc}", 502)

            ceiling = book.will_pay
            checked = sweeps.swept_at(connection, book.work_id, scope=scope)
            # Where each copy sits among the others. The rank reads what is
            # listed in this scope; the range reads every copy ever recorded,
            # which is a wider question — and both come from one derivation of
            # the edition set, so there is no second one to disagree with it.
            for_sale, seen = copies.populations(connection, book, scope=scope)
            placed = standing.standings(for_sale, seen)

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
            "scope": scope,
            "ceiling": ceiling,
            # The verdict per copy, worked out once here rather than in the
            # template. Decision 43: derived on read, never stored.
            "verdict": {copy.item_id: copy.against(ceiling) for copy in for_sale},
            # Deliberately independent of the ceiling. A rank is about the
            # market and a ceiling is about you, so a copy over your limit
            # still counts in what the copies under it are cheaper *than*.
            "standing": placed,
            # The same numbers lifted to the book. A range is a property of a
            # condition class, so stating it per copy says one fact once per
            # copy — eight times on a twelve-copy book.
            "markets": standing.markets(placed),
            "is_isbn": normalise(book.search_query) is not None,
        }
        return templates.TemplateResponse(
            request, "book.html", context, status_code=error[1] if error else 200
        )

    @router.post(CEILING_PATH, response_class=HTMLResponse)
    def set_ceiling(
        request: Request,
        book_id: int,
        ceiling: Annotated[str, Form()] = "",
        currency: Annotated[str, Form()] = "USD",
    ) -> HTMLResponse:
        """Set or clear what this book is worth paying, delivered.

        A redirect rather than a rendered page, so a refresh does not re-post
        the form — and so the answer comes back through the one route that
        knows how to draw a book.
        """
        with closing(open_database()) as connection:
            try:
                wantlist.set_ceiling(connection, book_id, ceiling, currency)
            except LookupError:
                return HTMLResponse("That book is not on the want-list.", 404)
            except ValueError as exc:
                return HTMLResponse(str(exc), 400)
        return RedirectResponse(f"/book/{book_id}", status_code=303)

    return router

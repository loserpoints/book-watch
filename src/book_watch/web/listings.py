"""One book: what is for sale, what it costs, and the most I will pay.

**Opening a book searches eBay, and that is the design rather than a
placeholder** — an earlier version of this docstring called it one. There is
no other reason to click a book's title than to find out what is listed
*now*, and the version that searched only on a book's first-ever view showed
copies that may have sold days earlier. A sweep is gated to one
an hour per scope so the list holds still long enough to act on, and a button
ignores the gate on demand.

It never fetches a listing's details: measured at 0.51s each, fifty of them
is twenty-five seconds, and that work belongs to the background pass.

The ad-hoc `/search` page shares this module because it asks the same
question of eBay without a book on the list behind it. The want-list and its
checking live in `wantlist`; the search wiring both need is in `searching`.
"""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from book_watch import copies, covers, enrichment, standing, sweeps, wantlist
from book_watch.config import MissingCredentialError
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Scope,
)
from book_watch.isbn import normalize
from book_watch.web import assets, book_view, filters
from book_watch.web.searching import LazyBrowseSearch, SearchFn
from book_watch.web.wantlist import ConnectFn, from_htmx, open_configured_database

SEARCH_PATH = "/search"
BOOK_PATH = "/book/{book_id}"
CEILING_PATH = "/book/{book_id}/ceiling"

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _book_url(
    book_id: int,
    *,
    everywhere: bool,
    limit: int = DEFAULT_LIMIT,
    newest: bool = False,
    refresh: bool = False,
) -> str:
    """A book's page, in the scope and order it was viewed in.

    The order rides along on every link the page makes, so changing scope or
    checking again keeps it (S62). Opening a book fresh shows cheapest first.
    """
    query = [("everywhere", "1")] if everywhere else []
    if limit != DEFAULT_LIMIT:
        query.append(("limit", str(limit)))
    if newest:
        query.append(("sort", "newest"))
    if refresh:
        query.append(("refresh", "1"))
    return f"/book/{book_id}" + ("?" + urlencode(query) if query else "")


def build_router(
    search: SearchFn | None = None,
    connect: ConnectFn | None = None,
    enrich: enrichment.EnrichFn | None = None,
) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    filters.register(templates.env)
    assets.register(templates.env)
    templates.env.filters["cover_url"] = covers.url
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )
    start_enrichment: enrichment.EnrichFn = (
        enrich if enrich is not None else enrichment.configured(open_database)
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
            "is_isbn": normalize(query) is not None,
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
        # Keyword, not GTIN. Sellers put the ISBN in
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
        sort: str = "",
    ) -> HTMLResponse:
        """What is for sale for one book, graded by how sure we are.

        The page reads the store. It searches eBay only when this book has
        never been searched for, or when asked to refresh. It never fetches a
        listing's detail: measured at 0.51s each, fifty of them is
        twenty-five seconds, and that work belongs to the background.
        """
        # Nothing is persisted. A toggle that quietly changed what every later
        # visit searched for would be a setting wearing a link's clothes, and
        # settings are #72.
        scope: Scope = "everywhere" if everywhere else "us"
        newest = sort == "newest"
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
            # may have sold days earlier and hid copies listed since.
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
                else:
                    if refresh:
                        # Searched, so now show the page at an address without
                        # `refresh`: a reload of it, or a return to it, must
                        # not search eBay again (S45). The visit is recorded
                        # by the page this redirects to.
                        return RedirectResponse(
                            _book_url(
                                book_id,
                                everywhere=bool(everywhere),
                                limit=limit,
                                newest=newest,
                            ),
                            status_code=303,
                        )

            # Recorded after the search, so a copy this visit's own search
            # found is never new on the want-list afterwards: I have seen it.
            wantlist.look(connection, book_id, datetime.now(UTC))
            book = wantlist.get(connection, book_id)
            # Marked against the visit before this one (S39, #142).
            since = book.looked_before_this

            ceiling = book.will_pay
            checked = sweeps.swept_at(connection, book.work_id, scope=scope)
            # Where each copy sits among the others. The rank reads what is
            # listed in this scope; the range reads every copy ever recorded,
            # which is a wider question — and both come from one derivation of
            # the edition set, so there is no second one to disagree with it.
            for_sale, seen = copies.populations(connection, book, scope=scope)
            placed = standing.standings(for_sale, seen)

        # Scheduled after the response is written, never before it: examining
        # fifty copies is twenty-five seconds of eBay, and this page owes an
        # answer in two.
        #
        # The condition is "has a pass finished", not "is there a copy eBay
        # has never been asked about". The second was the original and it was
        # wrong in a way nothing caught: after the first pass there is never
        # an unasked copy, so enrichment ran once per book and never again —
        # and every later fix to what a pass does was dead code in production
        # while passing every test, because tests start from an empty
        # database and production does not.
        if book.enriched_at is None:
            background.add_task(enrichment.queued(start_enrichment, book.work_id))

        shown = [copy for copy in for_sale if copy.tier != "excluded"]
        if newest:
            # Within each group, since the groups are split below. A copy
            # with no listing date says nothing about newness, so it goes last.
            shown.sort(
                key=lambda copy: (
                    copy.listed is None,
                    -copy.listed.timestamp() if copy.listed else 0,
                )
            )
        verdicts = {copy.item_id: copy.against(ceiling) for copy in for_sale}
        listed_prices = standing.prices(for_sale)
        seen_prices = standing.prices(seen)
        market_list = standing.markets(placed)

        def rows(tier_wanted: bool) -> list[dict]:
            return [
                book_view.copy_row(
                    copy,
                    verdicts[copy.item_id],
                    placed.get(copy.item_id),
                    ceiling,
                    listed_prices,
                    new=copies.is_new(copy, since),
                )
                for copy in shown
                if (copy.tier == "certain") == tier_wanted
            ]

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
            # template. Derived on read, never stored.
            "verdict": verdicts,
            # Deliberately independent of the ceiling. A rank is about the
            # market and a ceiling is about you, so a copy over your limit
            # still counts in what the copies under it are cheaper *than*.
            "standing": placed,
            # The same numbers lifted to the book. A range is a property of a
            # condition class, so stating it per copy says one fact once per
            # copy — eight times on a twelve-copy book.
            "markets": market_list,
            "is_isbn": not book.searched_as_text,
            # The same facts, as the system's pieces take them (S34).
            "copy_rows": rows(True),
            "newest": newest,
            "urls": {
                name: _book_url(book.id, limit=limit, **choice)
                for name, choice in {
                    "us": {"everywhere": False, "newest": newest},
                    "everywhere": {"everywhere": True, "newest": newest},
                    "refresh": {
                        "everywhere": bool(everywhere),
                        "newest": newest,
                        "refresh": True,
                    },
                    "cheapest": {"everywhere": bool(everywhere)},
                    "newest": {"everywhere": bool(everywhere), "newest": True},
                }.items()
            },
            "maybe_rows": rows(False),
            "market_lines": [
                book_view.market_line(market, seen_prices, ceiling)
                for market in market_list
            ],
            "ceiling_text": book_view.money(ceiling) if ceiling else None,
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

        From the sheet, through htmx, the page reloads in place instead (S45).
        A redirect would add a second entry for the same book to the history,
        so back would show the book again rather than the want list. A limit
        that cannot be read is answered inside the sheet, which stays open.
        """
        htmx = from_htmx(request)
        with closing(open_database()) as connection:
            try:
                wantlist.set_ceiling(connection, book_id, ceiling, currency)
            except LookupError:
                return HTMLResponse("That book is not on the want-list.", 404)
            except ValueError as exc:
                if htmx:
                    return templates.TemplateResponse(
                        request, "_sheet_error.html", {"error": str(exc)}
                    )
                return HTMLResponse(str(exc), 400)
        if htmx:
            return Response(status_code=204, headers={"HX-Refresh": "true"})
        return RedirectResponse(f"/book/{book_id}", status_code=303)

    return router

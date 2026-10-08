"""The want-list screens: add a book, see the list, remove an entry.

A connection per request, opened and closed around it. SQLite connections
belong to the thread that made them and FastAPI runs synchronous handlers on a
pool, so a single shared connection would fail the moment two requests landed
on different threads. Opening one is measured in microseconds.

Migrations run on every connection. That is one small SELECT against a table
of four rows, and it means the schema is correct on a volume that was empty a
moment ago without a startup hook that could be skipped.

Adding a book makes **one** Open Library request — a title search, or one
number looked up. That is well inside the Open Library limits. The
ten to fifteen requests a book eventually costs are for the numbers sellers
declare in its listings, and those run in the background because they cannot
run while somebody waits.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from book_watch import (
    abebooks,
    covers,
    daily,
    db,
    enrichment,
    monitoring,
    purchases,
    standing,
    sweeps,
    wantlist,
)
from book_watch.config import MissingCredentialError, load_database_path
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import DEFAULT_LIMIT
from book_watch.isbn import normalize
from book_watch.openlibrary import (
    CallBudget,
    OpenLibraryClient,
    OpenLibraryUnavailable,
)
from book_watch.web import assets, book_view, filters, list_view
from book_watch.web.searching import LazyBrowseSearch, SearchFn

TEMPLATES_DIR = Path(__file__).parent / "templates"
CHECK_ALL_PATH = "/books/check"
CHECK_ONE_PATH = "/books/{book_id}/check"
ROW_PATH = "/books/{book_id}/row"
BAR_PATH = "/books/bar"

ConnectFn = Callable[[], sqlite3.Connection]


class LazyCatalog:
    """Holds one Open Library client for the life of the application.

    One, rather than one per request, and this is load-bearing. The pause
    between Open Library requests is kept *inside* the client, as
    a note of when it last spoke. A fresh client per request forgets that
    every time, so the pacing would silently never happen — the promise would
    still be in the code and no longer true of the process.

    Built on first use for the same reason the eBay client is
    (`listings.LazyBrowseSearch`): nothing that could fail should run while
    the compliance endpoint is trying to boot.

    The pause itself is not held here — it lives in the client's module, so
    it survives however many of these exist. What this avoids is the *other*
    half of that bug: an httpx client rebuilt per request.
    """

    def __init__(self, connect: ConnectFn) -> None:
        self._connect = connect
        self._client: OpenLibraryClient | None = None

    def _open(self) -> OpenLibraryClient:
        if self._client is None:
            self._client = OpenLibraryClient(CallBudget(self._connect))
        return self._client

    def identify_isbn(self, isbn: str):
        return self._open().identify_isbn(isbn)

    def search_works(self, title: str, author: str | None = None):
        return self._open().search_works(title, author)

    def work_cover(self, work_id: str):
        return self._open().work_cover(work_id)


def open_configured_database() -> sqlite3.Connection:
    """Connect using the configured path, migrating if needed.

    Deferred to the first request for the same reason the eBay client is:
    the compliance endpoint must start even when
    everything else is misconfigured.
    """
    connection = db.connect(load_database_path())
    db.migrate(connection)
    return connection


def from_htmx(request: Request) -> bool:
    """Whether htmx sent this, so the answer can be a piece of the page that
    leaves the history alone rather than a whole new page (S45)."""
    return request.headers.get("HX-Request") == "true"


#: The page address for the want list narrowed to books with a copy under
#: their limit (S60, #132). It lives in the address, not in the database or
#: the device, so it survives opening a book and going back, and opening the
#: app fresh shows everything.
UNDER_LIMIT_URL = "/?show=under"


def list_changed(response: HTMLResponse) -> HTMLResponse:
    """Tell the page the list changed, so the header asks for itself again.

    After the swap settles, so the header's request carries the runner as it
    now is, and knows whether a check is still running (S67, #244).
    """
    response.headers["HX-Trigger-After-Settle"] = "list-changed"
    return response


def wants_under(request: Request) -> bool:
    """Whether this request is for the list narrowed to books under a limit.

    Asked by the address itself, or, for a piece htmx fetches from another
    path, by the address of the page it came from. That is how deleting a
    book keeps the filter on without the delete knowing about it. An address
    that names a choice wins: switching the filter off is asked from a page
    whose address still has it on.
    """
    if "show" in request.query_params:
        return request.query_params["show"] == "under"
    current = request.headers.get("HX-Current-URL", "")
    return "show=under" in urlsplit(current).query.split("&")


#: How the want list can be ordered (S69, #217). "added" is the newest book
#: first, as the list always was; "cheapest" is by the "from $X" each row
#: shows. It lives in the page address, like the filter.
Sort = Literal["added", "cheapest"]


def wants_sort(request: Request) -> Sort:
    """The order this request is for, asked the same two ways as the filter."""
    if "sort" in request.query_params:
        return "cheapest" if request.query_params["sort"] == "cheapest" else "added"
    current = request.headers.get("HX-Current-URL", "")
    if "sort=cheapest" in urlsplit(current).query.split("&"):
        return "cheapest"
    return "added"


def view_query(under: bool, sort: Sort) -> str:
    """The page address's query for a filter and an order, empty for the
    defaults, so opening the app plain shows everything, newest first."""
    parts = (["show=under"] if under else []) + (
        ["sort=cheapest"] if sort == "cheapest" else []
    )
    return ("?" + "&".join(parts)) if parts else ""


def views(under: bool, sort: Sort) -> dict[str, dict[str, str]]:
    """Where each choice in the header goes: the page address it replaces the
    current one with, and the list it fetches. One place, so the filter keeps
    the order and the order keeps the filter."""

    def to(new_under: bool, new_sort: Sort) -> dict[str, str]:
        # The fetch names both choices, since it is asked from a page whose
        # address still holds the old ones.
        show = "under" if new_under else "all"
        return {
            "page": "/" + view_query(new_under, new_sort),
            "fetch": f"/books/list?show={show}&sort={new_sort}",
        }

    return {
        "under_on": to(True, sort),
        "under_off": to(False, sort),
        "cheapest": to(under, "cheapest"),
        "added": to(under, "added"),
    }


def in_order(books: list, glances: dict, sort: Sort) -> list:
    """The books in the order asked for. Cheapest goes by each row's own
    "from $X", so the order can't disagree with what the rows say, and books
    with no price go last, newest first among them."""
    if sort != "cheapest":
        return books

    def price(book) -> tuple[bool, Decimal]:
        glance = glances.get(book.id)
        lead = glance.headline if glance is not None else None
        if lead is None:
            return (True, Decimal(0))
        return (False, lead.cheapest.amount)

    return sorted(books, key=price)


def build_router(
    connect: ConnectFn | None = None,
    catalog: LazyCatalog | None = None,
    search: SearchFn | None = None,
    enrich: enrichment.EnrichFn | None = None,
    read_abebooks: abebooks.Reader | None = None,
) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    filters.register(templates.env)
    assets.register(templates.env)
    templates.env.filters["cover_url"] = covers.url
    templates.env.globals["want_row"] = list_view.row
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )
    open_library = catalog if catalog is not None else LazyCatalog(open_database)
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()
    start_enrichment: enrichment.EnrichFn = (
        enrich if enrich is not None else enrichment.configured(open_database)
    )
    budget = CallBudget(open_database)

    def throttled(books: list) -> bool:
        """Whether a book waiting to be examined is waiting on the ceiling.

        Counted only when some book is waiting, so a list with nothing
        outstanding reads nothing more than it did.
        """
        return any(book.being_enriched for book in books) and budget.exhausted()

    def at_a_glance(connection: sqlite3.Connection, books: list) -> dict[int, object]:
        """What each book's market looks like, read from the store alone.

        No request is made here. Opening this page is not a request to search
        ten books — that is what the button is for, and a page
        that spent ten seconds before rendering would be a worse page.
        """
        return {book.id: standing.glance(connection, book) for book in books}

    def under_limit(glances: dict[int, object]) -> set[int]:
        """The books whose row price is green: a copy at or under the limit.

        The row's own verdict, so the filter can never disagree with what the
        row shows. No limit, or a price without shipping, is never under.
        """
        return {
            book_id
            for book_id, glance in glances.items()
            if glance.headline is not None and glance.headline.verdict == "under"
        }

    def out_of_date(connection: sqlite3.Connection, books: list) -> int:
        """How many books "Check N" would check: the same gate `check_all` uses,
        so the count on the button is what pressing it costs."""
        return sum(
            1
            for book in books
            if sweeps.due_for_sweep(connection, book.work_id, scope="us")
        )

    def hidden_digging(books: list, under_ids: set[int], under: bool) -> bool:
        """Whether a book the "Under limit" filter hides is digging. It has no
        row to ask for itself, so the list asks instead until none is, and may
        then show it (S68, #240)."""
        return (
            under
            and bool(under_ids)
            and any(
                list_view.examining(book) == "digging"
                for book in books
                if book.id not in under_ids
            )
        )

    def render_list(
        request: Request,
        *,
        checking: int | None = None,
        template: str = "_list.html",
        under: bool | None = None,
    ) -> HTMLResponse:
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
            glances = at_a_glance(connection, books)
            stale = out_of_date(connection, books)
            morning = daily.status(connection, datetime.now(UTC))
            bought = purchases.everything(connection)
        under_ids = under_limit(glances)
        if under is None:
            under = wants_under(request)
        # Adding a book shows it at the top, so the order goes back to added.
        order = wants_sort(request) if checking is None else "added"
        return templates.TemplateResponse(
            request,
            template,
            {
                # An empty add sheet, for `_added.html`.
                "isbn": "",
                "title": "",
                "author": "",
                "books": in_order(books, glances, order),
                "glances": glances,
                "checking": checking,
                "stale": stale,
                "sort": order,
                "views": views(under and bool(under_ids), order),
                "throttled": throttled(books),
                "daily": morning,
                "under_ids": under_ids,
                # Nothing under a limit shows everything, never an empty list.
                "filtering": under and bool(under_ids),
                "hidden_digging": hidden_digging(books, under_ids, under),
                # Below the list, folded (S71, #223).
                "bought": [list_view.bought_row(p) for p in bought],
                "bought_total": list_view.bought_total(bought),
            },
        )

    def render_page(
        request: Request,
        *,
        error: str | None = None,
        note: str | None = None,
        offer_override: bool = False,
        candidates: list | None = None,
        isbn: str = "",
        title: str = "",
        author: str = "",
        status_code: int = 200,
        checking: int | None = None,
    ) -> HTMLResponse:
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
            glances = at_a_glance(connection, books)
            stale = out_of_date(connection, books)
            morning = daily.status(connection, datetime.now(UTC))
            on_list = wantlist.listed_works(connection) if candidates else set()
            bought = purchases.everything(connection)
        under_ids = under_limit(glances)
        order = wants_sort(request) if checking is None else "added"
        filtering = wants_under(request) and bool(under_ids)
        # Through htmx, only the sheet comes back, and it comes back as a
        # success: htmx does not swap an error status in, and the error is
        # the answer the sheet exists to show (S45).
        htmx = from_htmx(request)
        return templates.TemplateResponse(
            request,
            "_add_sheet.html" if htmx else "wantlist.html",
            {
                "books": in_order(books, glances, order),
                "glances": glances,
                "stale": stale,
                "sort": order,
                "views": views(filtering, order),
                "throttled": throttled(books),
                "daily": morning,
                "under_ids": under_ids,
                "filtering": filtering,
                "hidden_digging": hidden_digging(
                    books, under_ids, wants_under(request)
                ),
                # The book just added, which starts checking itself on load.
                # Adding a book is an explicit act, so this is not an
                # exception to "nothing sweeps on page load" — and it means a
                # book you just added never shows as unchecked, which is the
                # state that reads worst on a list.
                "checking": checking,
                "bought": [list_view.bought_row(p) for p in bought],
                "bought_total": list_view.bought_total(bought),
                "error": error,
                "note": note,
                "offer_override": offer_override,
                "candidates": [
                    list_view.candidate(found, on_list) for found in candidates or []
                ],
                "isbn": isbn,
                "title": title,
                "author": author,
            },
            status_code=200 if htmx else status_code,
        )

    def store(request: Request, put_on_list, duplicate_of: str) -> HTMLResponse:
        try:
            with closing(open_database()) as connection:
                added = put_on_list(connection)
        except wantlist.DuplicateBook:
            monitoring.action("add", outcome="duplicate")
            return render_page(
                request,
                error=f"{duplicate_of} is already on the list.",
                status_code=409,
            )
        monitoring.action("add", book=added.id, title=added.name)
        # The whole page comes back, so the form clears and the new row shows
        # — already checking itself, because the first thing you want to know
        # about a book you just added is whether anybody is selling it.
        if not from_htmx(request):
            return render_page(request, checking=added.id)
        # Through htmx the list is swapped in place and the sheet emptied and
        # closed, so adding a book leaves nothing in the history (S45).
        # The whole list shows, filter off, so the new book is there to see:
        # it has no price yet, and would otherwise vanish as it was added.
        response = render_list(
            request, checking=added.id, template="_added.html", under=False
        )
        response.headers["HX-Replace-Url"] = "/"
        response.headers["HX-Retarget"] = "#want-list"
        response.headers["HX-Reswap"] = "outerHTML"
        response.headers["HX-Trigger"] = "added"
        return response

    @router.get("/", response_class=HTMLResponse)
    def want_list(request: Request) -> HTMLResponse:
        response = render_page(request)
        # Asked for again on back, not taken from the browser's cache: in
        # Chromium, back from a book's page showed the list as it was before
        # that book was checked (S67, #244). "no-cache" was not enough, since
        # back may show a cached page without revalidating it; only
        # "no-store" makes it ask.
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get("/books/list", response_class=HTMLResponse)
    def the_list(request: Request) -> HTMLResponse:
        """The list alone, for the switch between all books and those under a
        limit. The switch replaces the page address, so it adds no history."""
        return render_list(request)

    @router.post("/books", response_class=HTMLResponse)
    def add_book(
        request: Request,
        isbn: str = Form(""),
        title: str = Form(""),
        author: str = Form(""),
        override: str = Form(""),
    ) -> HTMLResponse:
        monitoring.handling("add")
        typed = isbn.strip()
        wanted = title.strip()
        by = author.strip()

        if not typed and not wanted:
            return render_page(
                request,
                error="Enter a title, or an ISBN.",
                title=wanted,
                author=by,
                status_code=400,
            )

        if typed:
            return _add_by_number(request, typed, wanted, by, bool(override))
        return _search_by_title(request, wanted, by)

    def _add_by_number(
        request: Request, typed: str, title: str, author: str, override: bool
    ) -> HTMLResponse:
        normalized = normalize(typed)

        if normalized is None:
            if not override:
                # Not an error yet — an offer. The check digit says this is not
                # an ISBN, which is usually a typo and occasionally a book that
                # never had one. Only the person holding the book knows which.
                return render_page(
                    request,
                    error=(
                        f"“{typed}” is not a valid ISBN — its check digit does "
                        "not match. That is usually a typo."
                    ),
                    offer_override=True,
                    isbn=typed,
                    title=title,
                    author=author,
                    status_code=400,
                )
            # Stored as typed, spaces and all: it is not an ISBN, so
            # normalizing it would be pretending otherwise.
            return store(
                request,
                lambda c: wantlist.add(c, typed, title or None),
                duplicate_of=typed,
            )

        if override:
            # A valid number Open Library did not recognize, added anyway
            # because the person holding the book says it is real.
            return store(
                request,
                lambda c: wantlist.add(c, normalized, title or None),
                duplicate_of=normalized,
            )

        try:
            identity = open_library.identify_isbn(normalized)
        except OpenLibraryUnavailable:
            return render_page(
                request,
                error=(
                    "Open Library could not be reached, so there is nothing to "
                    "check this number against right now."
                ),
                offer_override=True,
                isbn=normalized,
                title=title,
                author=author,
                status_code=503,
            )

        if identity is None:
            return render_page(
                request,
                error=(
                    f"Open Library has no record of {normalized}. That is "
                    "usually a mistyped digit — and occasionally a real book "
                    "it simply does not hold."
                ),
                offer_override=True,
                isbn=normalized,
                title=title,
                author=author,
                status_code=404,
            )

        # Read the title back, so a number that names the wrong
        # book is caught now rather than by a coincidence a week later.
        return store(
            request,
            lambda c: wantlist.add_identified(
                c,
                title=identity.title,
                author=author or None,
                openlibrary_work_id=identity.work_id,
                isbn=normalized,
                edition_cover=identity.cover_id,
            ),
            duplicate_of=normalized,
        )

    def _search_by_title(request: Request, title: str, author: str) -> HTMLResponse:
        try:
            candidates = open_library.search_works(title, author or None)
        except OpenLibraryUnavailable:
            return render_page(
                request,
                error=(
                    "Open Library could not be reached, so there is nothing to "
                    "search right now. An ISBN can still be added by hand."
                ),
                title=title,
                author=author,
                status_code=503,
            )

        if not candidates:
            return render_page(
                request,
                error=(
                    f"Nothing found for “{title}”. Try fewer words, or a "
                    "different spelling, or add it by ISBN."
                ),
                title=title,
                author=author,
                status_code=404,
            )
        return render_page(
            request,
            note="Which one?",
            candidates=candidates,
            title=title,
            author=author,
        )

    @router.post("/books/chosen", response_class=HTMLResponse)
    def add_chosen(
        request: Request,
        title: str = Form(...),
        author: str = Form(""),
        work_id: str = Form(""),
        cover_id: str = Form(""),
    ) -> HTMLResponse:
        """Put the candidate the person picked on the list.

        The fields come back from the form they were rendered into rather than
        being fetched again. That saves a second request to a service that asks
        for low volume, and it is safe here only because there is one user and
        no authentication. Worth revisiting if either changes.
        """
        monitoring.handling("add")
        return store(
            request,
            lambda c: wantlist.add_identified(
                c,
                title=title.strip(),
                author=author.strip() or None,
                openlibrary_work_id=work_id.strip() or None,
                work_cover=int(cover_id) if cover_id.strip().isdigit() else None,
            ),
            duplicate_of=title.strip(),
        )

    @router.get("/books/{book_id}/cover")
    def cover(book_id: int) -> Response:
        """Send the browser to this book's cover, learning which one it is first.

        Only reached for a book whose cover nobody has asked about yet: once
        the answer is stored, the list links to Open Library's image directly
        and never comes here again. So the Open Library request this makes —
        two at most, for a book known only by an edition with no cover of its
        own — happens once per book, after the list has already rendered.

        A 404 means there is nothing to show, for whatever reason, and the
        page shows its placeholder. If the reason was Open Library being
        unreachable, nothing was written and the next view asks again.
        """
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                return Response(status_code=404)
            if book.cover is None and book.cover_asked_at is None:
                monitoring.handling("cover", book.id, book.name)
                covers.look_up(connection, open_library, book.work_id)
                try:
                    book = wantlist.get(connection, book_id)
                except LookupError:
                    # Taken off the list while its cover was being asked for.
                    return Response(status_code=404)
        if book.cover is None:
            return Response(status_code=404)
        return RedirectResponse(covers.url(book.cover), status_code=302)

    @router.delete("/books/{book_id}", response_class=HTMLResponse)
    def remove_book(request: Request, book_id: int) -> HTMLResponse:
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                book = None
            wantlist.remove(connection, book_id)
        if book is not None:
            monitoring.action("remove", book=book.id, title=book.name)
        # Deleting something already gone is not an error worth showing: the
        # list is the answer to "what is on the list", and it is now correct.
        return taken_off(render_list(request))

    def taken_off(response: HTMLResponse) -> HTMLResponse:
        """The list in place of the old one, with the take-off sheet told to
        close over it (S71)."""
        response.headers["HX-Retarget"] = "#want-list"
        response.headers["HX-Reswap"] = "outerHTML"
        response.headers["HX-Trigger"] = "taken-off"
        return response

    def off_sheet(
        request: Request,
        book: wantlist.Entry,
        *,
        suggestion: purchases.Suggestion | None = None,
        where: str = "ebay",
        shop: str = "",
        paid: str = "",
        bought_on: str = "",
        error: str | None = None,
    ) -> HTMLResponse:
        today = datetime.now(daily.ZONE).date().isoformat()
        suggested = None
        if suggestion is not None:
            ago = filters.since(suggestion.opened_at)
            suggested = (
                "Filled in from the copy you opened "
                + ("just now" if ago == "just now" else f"{ago} ago")
                + ". Change anything that's different."
            )
            if suggestion.paid is None:
                suggested += " Its shipping wasn't known, so say what you paid."
        limit = book.will_pay
        response = templates.TemplateResponse(
            request,
            "_off_sheet.html",
            {
                "book": book,
                "suggested": suggested,
                "where": where,
                "shop": shop,
                "paid": paid,
                "bought_on": bought_on or today,
                "today": today,
                "limit_text": book_view.money(limit) if limit else None,
                "error": error,
            },
        )
        # Opened only once it holds this book, never showing the last one.
        response.headers["HX-Trigger-After-Settle"] = '{"sheet-ready": "off-sheet"}'
        return response

    @router.get("/books/{book_id}/off", response_class=HTMLResponse)
    def take_off(request: Request, book_id: int) -> HTMLResponse:
        """The sheet the trash opens, filled in from the copy of this book
        last opened from the app (S71, #223)."""
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                # Gone already, from another tab: the list says so.
                return taken_off(render_list(request))
            suggestion = purchases.suggestion(connection, book)
        if suggestion is None:
            return off_sheet(request, book)
        return off_sheet(
            request,
            book,
            suggestion=suggestion,
            where=suggestion.marketplace,
            paid=f"{suggestion.paid.amount:.2f}" if suggestion.paid else "",
        )

    @router.post("/books/{book_id}/bought", response_class=HTMLResponse)
    def mark_bought(
        request: Request,
        book_id: int,
        where: str = Form("ebay"),
        shop: str = Form(""),
        paid: str = Form(""),
        bought_on: str = Form(""),
    ) -> HTMLResponse:
        """Record the purchase and take the book off the list. A refusal
        comes back in the sheet with what was typed."""
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                book = None
            if book is not None:
                today = datetime.now(daily.ZONE).date()
                try:
                    amount = purchases.amount(paid)
                    if where not in (*purchases.MARKETPLACES, "other"):
                        raise purchases.Refused("Say where you bought it.")
                    if where == "other" and not shop.strip():
                        raise purchases.Refused("Say which shop or site.")
                    try:
                        on = date.fromisoformat(bought_on.strip())
                    except ValueError:
                        raise purchases.Refused("Say when you bought it.") from None
                    if on > today:
                        raise purchases.Refused("That date hasn't happened yet.")
                except purchases.Refused as refused:
                    return off_sheet(
                        request,
                        book,
                        where=where,
                        shop=shop,
                        paid=paid,
                        bought_on=bought_on,
                        error=str(refused),
                    )
                purchases.buy(
                    connection,
                    book_id,
                    paid=amount,
                    # The sheet asks in dollars, as every limit is set.
                    currency="USD",
                    marketplace=None if where == "other" else where,
                    shop=shop.strip() if where == "other" else None,
                    bought_on=on,
                )
                monitoring.action(
                    "bought",
                    book=book.id,
                    title=book.name,
                    where=shop.strip() if where == "other" else where,
                    paid=amount,
                )
        return taken_off(render_list(request))

    @router.post("/books/{book_id}/opened")
    def copy_opened(
        request: Request, book_id: int, m: str = "", item: str = ""
    ) -> Response:
        """Which copy of this book was just opened, sent alongside the tap
        that opens it (S71). Only ever a hint for the bought sheet."""
        with closing(open_database()) as connection:
            purchases.opened(connection, book_id, m, item, datetime.now(UTC))
        return Response(status_code=204)

    def render_step(
        request: Request,
        *,
        book,
        glance,
        state: str,
        queue: list[int],
        force: bool,
        done: int,
    ) -> HTMLResponse:
        """One step of the walk: the next runner, plus the rows that changed."""
        next_book = next_glance = None
        if queue:
            with closing(open_database()) as connection:
                next_book = wantlist.get(connection, queue[0])
                next_glance = standing.glance(connection, next_book)
        return list_changed(
            templates.TemplateResponse(
                request,
                "_checked.html",
                {
                    "book": book,
                    "glance": glance,
                    "state": state,
                    "throttled": throttled([b for b in (book, next_book) if b]),
                    "next_book": next_book,
                    "next_glance": next_glance,
                    "next_id": queue[0] if queue else None,
                    "queue": queue[1:],
                    "remaining": len(queue),
                    "force": force,
                    # Carried along the chain rather than recounted, because each
                    # step is a separate request and knows only what it was told.
                    "done": done,
                    "message": (
                        None
                        if queue
                        else f"Checked {done} book{'' if done == 1 else 's'}."
                    ),
                },
            )
        )

    @router.get(BAR_PATH, response_class=HTMLResponse)
    def the_bar(
        request: Request, walking: int = 0, done: int = 0, remaining: int = 0
    ) -> HTMLResponse:
        """The header over the list, as it stands now. Asked for by the page
        whenever the list changes. Reads the store only.

        `done` and `remaining` come from the runner while a check runs, so
        the button can say how far it has got (S69, #217)."""
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
            under_ids = under_limit(at_a_glance(connection, books))
            stale = out_of_date(connection, books)
        filtering = wants_under(request) and bool(under_ids)
        order = wants_sort(request)
        return templates.TemplateResponse(
            request,
            "_list_bar_contents.html",
            {
                "total": len(books),
                "stale": stale,
                "under_ids": under_ids,
                "filtering": filtering,
                "sort": order,
                "views": views(filtering, order),
                "walking": bool(walking),
                # Without the runner's count, it says only that a check runs.
                "progress": (done + 1, done + remaining)
                if walking and remaining
                else None,
            },
        )

    @router.get(CHECK_ALL_PATH, response_class=HTMLResponse)
    def check_all(request: Request, force: int = 0) -> HTMLResponse:
        """Work out which books need checking, and start the walk.

        The queue is built here rather than passed in, so a book already
        checked within the hour never enters it and its row never flickers
        through a state it was not in. That is also why most of a walk is
        instant: the gate usually leaves two or three books in the queue.
        """
        with closing(open_database()) as connection:
            queue = [
                book.id
                for book in wantlist.all_books(connection)
                if force or sweeps.due_for_sweep(connection, book.work_id, scope="us")
            ]
        monitoring.action("check", all=bool(force), books=len(queue))
        if not queue:
            # Doing nothing is the correct answer and it still has to be said.
            # Silence here reads as a broken button, and every book being
            # inside the hour gate is exactly why nothing happened.
            # The header offered a check it didn't need, so it was out of
            # date. It is told to look again.
            return list_changed(
                templates.TemplateResponse(
                    request,
                    "_runner.html",
                    {
                        "next_id": None,
                        "message": (
                            "Everything is current — every book was checked "
                            "within the hour."
                        ),
                    },
                )
            )
        # Nothing has been checked yet, so there is no finished row — only
        # the first book moving into its checking state and a runner aimed at
        # that same book. Aiming it at the second is how the first was
        # skipped.
        return render_step(
            request,
            book=None,
            glance=None,
            state="checking",
            queue=queue,
            force=bool(force),
            done=0,
        )

    @router.get(CHECK_ONE_PATH, response_class=HTMLResponse)
    def check_one(
        request: Request,
        background: BackgroundTasks,
        book_id: int,
        queue: str = "",
        force: int = 0,
        done: int = 0,
    ) -> HTMLResponse:
        """Search for one book, then hand the walk to the next.

        A search that fails leaves this row saying so and the walk carries on.
        One dead book must not hide the other nine — and the failure is on the
        row it belongs to rather than on the run as a whole, because that is
        where it can be acted on.
        """
        rest = [int(part) for part in queue.split(",") if part.strip().isdigit()]
        state = "idle"
        with closing(open_database()) as connection:
            book = wantlist.get(connection, book_id)
            monitoring.handling("check", book.id, book.name)
            if force or sweeps.due_for_sweep(connection, book.work_id, scope="us"):
                try:
                    sweeps.check_ebay(
                        connection,
                        book.work_id,
                        run_search,
                        book.search_query,
                        DEFAULT_LIMIT,
                        "us",
                    )
                    connection.commit()
                except (MissingCredentialError, EbayError):
                    state = "failed"
            # Its own hour, and before the copies are examined, as on the
            # book's page. A failure shows there, not on this row.
            abebooks.check_book(connection, book, read_abebooks, force=bool(force))
            book = wantlist.get(connection, book_id)
            glance = standing.glance(connection, book)

        # New copies are examined straight away, as opening the book does.
        # Before this, only opening the book started the pass, so a book
        # checked from here said "digging" until somebody opened it (#129).
        if (
            state != "failed"
            and book.being_enriched
            and not enrichment.busy(book.work_id)
        ):
            background.add_task(
                monitoring.carried(enrichment.queued(start_enrichment, book.work_id))
            )

        return render_step(
            request,
            book=book,
            glance=glance,
            state=state,
            queue=rest,
            force=bool(force),
            done=done + 1,
        )

    @router.get(ROW_PATH, response_class=HTMLResponse)
    def one_row(request: Request, book_id: int) -> HTMLResponse:
        """One row, as the list would draw it now. A digging row asks for
        this until it isn't digging. Reads the store only."""
        with closing(open_database()) as connection:
            try:
                book = wantlist.get(connection, book_id)
            except LookupError:
                # Removed while it was digging. An empty answer removes the
                # row, which is what the list would now show.
                return HTMLResponse("")
            glance = standing.glance(connection, book)
        held = throttled([book])
        response = templates.TemplateResponse(
            request,
            "_entry.html",
            {
                "book": book,
                "glance": glance,
                "state": "idle",
                "oob": False,
                "throttled": held,
            },
        )
        # The last answer a digging row asks for: its copies are examined, so
        # which books are under their limit may have changed with them.
        if list_view.examining(book, held) != "digging":
            list_changed(response)
        return response

    return router

"""The want-list screens: add a book, see the list, remove an entry.

A connection per request, opened and closed around it. SQLite connections
belong to the thread that made them and FastAPI runs synchronous handlers on a
pool, so a single shared connection would fail the moment two requests landed
on different threads. Opening one is measured in microseconds.

Migrations run on every connection. That is one small SELECT against a table
of four rows, and it means the schema is correct on a volume that was empty a
moment ago without a startup hook that could be skipped.

Adding a book makes **one** Open Library request — a title search, or one
number looked up. That is well inside what decision 7 calls a constraint. The
ten to fifteen requests a book eventually costs are for the numbers sellers
declare in its listings, and those run in the background because they cannot
run while somebody waits.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from book_watch import covers, db, standing, sweeps, wantlist
from book_watch.config import MissingCredentialError, load_database_path
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import DEFAULT_LIMIT
from book_watch.isbn import normalise
from book_watch.openlibrary import (
    CallBudget,
    OpenLibraryClient,
    OpenLibraryUnavailable,
)
from book_watch.web import filters
from book_watch.web.searching import LazyBrowseSearch, SearchFn

TEMPLATES_DIR = Path(__file__).parent / "templates"
CHECK_ALL_PATH = "/books/check"
CHECK_ONE_PATH = "/books/{book_id}/check"

ConnectFn = Callable[[], sqlite3.Connection]


class LazyCatalogue:
    """Holds one Open Library client for the life of the application.

    One, rather than one per request, and this is load-bearing. The pause
    between requests that decision 7 requires is kept *inside* the client, as
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

    Deferred to the first request for the same reason the eBay client is
    (decisions.md entry 24): the compliance endpoint must start even when
    everything else is misconfigured.
    """
    connection = db.connect(load_database_path())
    db.migrate(connection)
    return connection


def build_router(
    connect: ConnectFn | None = None,
    catalogue: LazyCatalogue | None = None,
    search: SearchFn | None = None,
) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    filters.register(templates.env)
    templates.env.filters["cover_url"] = covers.url
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )
    open_library = catalogue if catalogue is not None else LazyCatalogue(open_database)
    run_search: SearchFn = search if search is not None else LazyBrowseSearch()

    def at_a_glance(connection: sqlite3.Connection, books: list) -> dict[int, object]:
        """What each book's market looks like, read from the store alone.

        No request is made here. Opening this page is not a request to search
        ten books — that is what the button is for (decision 54), and a page
        that spent ten seconds before rendering would be a worse page.
        """
        return {book.id: standing.glance(connection, book) for book in books}

    def render_list(request: Request, *, checking: int | None = None) -> HTMLResponse:
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
            glances = at_a_glance(connection, books)
        return templates.TemplateResponse(
            request,
            "_list.html",
            {"books": books, "glances": glances, "checking": checking},
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
        return templates.TemplateResponse(
            request,
            "wantlist.html",
            {
                "books": books,
                "glances": glances,
                # The book just added, which starts checking itself on load.
                # Adding a book is an explicit act, so this is not an
                # exception to "nothing sweeps on page load" — and it means a
                # book you just added never shows as unchecked, which is the
                # state that reads worst on a list.
                "checking": checking,
                "error": error,
                "note": note,
                "offer_override": offer_override,
                "candidates": candidates,
                "isbn": isbn,
                "title": title,
                "author": author,
            },
            status_code=status_code,
        )

    def store(request: Request, put_on_list, duplicate_of: str) -> HTMLResponse:
        try:
            with closing(open_database()) as connection:
                added = put_on_list(connection)
        except wantlist.DuplicateBook:
            return render_page(
                request,
                error=f"{duplicate_of} is already on the list.",
                status_code=409,
            )
        # The whole page comes back, so the form clears and the new row shows
        # — already checking itself, because the first thing you want to know
        # about a book you just added is whether anybody is selling it.
        return render_page(request, checking=added.id)

    @router.get("/", response_class=HTMLResponse)
    def want_list(request: Request) -> HTMLResponse:
        return render_page(request)

    @router.post("/books", response_class=HTMLResponse)
    def add_book(
        request: Request,
        isbn: str = Form(""),
        title: str = Form(""),
        author: str = Form(""),
        override: str = Form(""),
    ) -> HTMLResponse:
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
        normalised = normalise(typed)

        if normalised is None:
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
            # normalising it would be pretending otherwise.
            return store(
                request,
                lambda c: wantlist.add(c, typed, title or None),
                duplicate_of=typed,
            )

        if override:
            # A valid number Open Library did not recognise, added anyway
            # because the person holding the book says it is real.
            return store(
                request,
                lambda c: wantlist.add(c, normalised, title or None),
                duplicate_of=normalised,
            )

        try:
            identity = open_library.identify_isbn(normalised)
        except OpenLibraryUnavailable:
            return render_page(
                request,
                error=(
                    "Open Library could not be reached, so there is nothing to "
                    "check this number against right now."
                ),
                offer_override=True,
                isbn=normalised,
                title=title,
                author=author,
                status_code=503,
            )

        if identity is None:
            return render_page(
                request,
                error=(
                    f"Open Library has no record of {normalised}. That is "
                    "usually a mistyped digit — and occasionally a real book "
                    "it simply does not hold."
                ),
                offer_override=True,
                isbn=normalised,
                title=title,
                author=author,
                status_code=404,
            )

        # Decision 32: read the title back, so a number that names the wrong
        # book is caught now rather than by a coincidence a week later.
        return store(
            request,
            lambda c: wantlist.add_identified(
                c,
                title=identity.title,
                author=author or None,
                openlibrary_work_id=identity.work_id,
                isbn=normalised,
                edition_cover=identity.cover_id,
            ),
            duplicate_of=normalised,
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
        no authentication (decision 25). Worth revisiting if either changes.
        """
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
                covers.look_up(connection, open_library, book.work_id)
                book = wantlist.get(connection, book_id)
        if book.cover is None:
            return Response(status_code=404)
        return RedirectResponse(covers.url(book.cover), status_code=302)

    @router.delete("/books/{book_id}", response_class=HTMLResponse)
    def remove_book(request: Request, book_id: int) -> HTMLResponse:
        with closing(open_database()) as connection:
            wantlist.remove(connection, book_id)
        # Deleting something already gone is not an error worth showing: the
        # list is the answer to "what is on the list", and it is now correct.
        return render_list(request)

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
        return templates.TemplateResponse(
            request,
            "_checked.html",
            {
                "book": book,
                "glance": glance,
                "state": state,
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
                    None if queue else f"Checked {done} book{'' if done == 1 else 's'}."
                ),
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
        if not queue:
            # Doing nothing is the correct answer and it still has to be said.
            # Silence here reads as a broken button, and every book being
            # inside the hour gate is exactly why nothing happened.
            return templates.TemplateResponse(
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
            if force or sweeps.due_for_sweep(connection, book.work_id, scope="us"):
                try:
                    sweeps.store(
                        connection,
                        book.work_id,
                        run_search(book.search_query, DEFAULT_LIMIT, scope="us"),
                        asked_for=DEFAULT_LIMIT,
                        scope="us",
                    )
                    connection.commit()
                except (MissingCredentialError, EbayError):
                    state = "failed"
                book = wantlist.get(connection, book_id)
            glance = standing.glance(connection, book)

        return render_step(
            request,
            book=book,
            glance=glance,
            state=state,
            queue=rest,
            force=bool(force),
            done=done + 1,
        )

    return router

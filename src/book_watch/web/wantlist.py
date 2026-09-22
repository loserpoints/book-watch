"""The want-list screens: add a book, see the list, remove an entry.

A connection per request, opened and closed around it. SQLite connections
belong to the thread that made them and FastAPI runs synchronous handlers on a
pool, so a single shared connection would fail the moment two requests landed
on different threads. Opening one is measured in microseconds.

Migrations run on every connection. That is one small SELECT against a table
of four rows, and it means the schema is correct on a volume that was empty a
moment ago without a startup hook that could be skipped.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch import db, wantlist
from book_watch.config import load_database_path
from book_watch.isbn import normalise

TEMPLATES_DIR = Path(__file__).parent / "templates"

ConnectFn = Callable[[], sqlite3.Connection]


def open_configured_database() -> sqlite3.Connection:
    """Connect using the configured path, migrating if needed.

    Deferred to the first request for the same reason the eBay client is
    (decisions.md entry 24): the compliance endpoint must start even when
    everything else is misconfigured.
    """
    connection = db.connect(load_database_path())
    db.migrate(connection)
    return connection


def build_router(connect: ConnectFn | None = None) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    open_database: ConnectFn = (
        connect if connect is not None else open_configured_database
    )

    def render_list(request: Request) -> HTMLResponse:
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
        return templates.TemplateResponse(request, "_list.html", {"books": books})

    def render_page(
        request: Request,
        *,
        error: str | None = None,
        offer_override: bool = False,
        isbn: str = "",
        title: str = "",
        status_code: int = 200,
    ) -> HTMLResponse:
        with closing(open_database()) as connection:
            books = wantlist.all_books(connection)
        return templates.TemplateResponse(
            request,
            "wantlist.html",
            {
                "books": books,
                "error": error,
                "offer_override": offer_override,
                "isbn": isbn,
                "title": title,
            },
            status_code=status_code,
        )

    @router.get("/", response_class=HTMLResponse)
    def want_list(request: Request) -> HTMLResponse:
        return render_page(request)

    @router.post("/books", response_class=HTMLResponse)
    def add_book(
        request: Request,
        isbn: str = Form(""),
        title: str = Form(""),
        override: str = Form(""),
    ) -> HTMLResponse:
        typed = isbn.strip()
        if not typed:
            return render_page(
                request, error="Enter an ISBN.", title=title, status_code=400
            )

        normalised = normalise(typed)
        if normalised is None and not override:
            # Not an error yet — an offer. The check digit says this is not an
            # ISBN, which is usually a typo and occasionally a book that never
            # had one. Only the person holding the book knows which.
            return render_page(
                request,
                error=(
                    f"“{typed}” is not a valid ISBN — its check digit does not "
                    "match. That is usually a typo."
                ),
                offer_override=True,
                isbn=typed,
                title=title,
                status_code=400,
            )

        # Overridden entries are stored as typed, spaces and all: they are not
        # ISBNs, so normalising them would be pretending otherwise.
        stored = normalised if normalised is not None else typed

        try:
            with closing(open_database()) as connection:
                wantlist.add(connection, stored, title.strip() or None)
        except wantlist.DuplicateBook:
            return render_page(
                request,
                error=f"{stored} is already on the list.",
                title=title,
                status_code=409,
            )

        # The whole page comes back, so the form clears and the new row shows.
        return render_page(request)

    @router.delete("/books/{book_id}", response_class=HTMLResponse)
    def remove_book(request: Request, book_id: int) -> HTMLResponse:
        with closing(open_database()) as connection:
            wantlist.remove(connection, book_id)
        # Deleting something already gone is not an error worth showing: the
        # list is the answer to "what is on the list", and it is now correct.
        return render_list(request)

    return router

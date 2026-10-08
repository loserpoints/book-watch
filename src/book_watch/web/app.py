"""Builds the application out of its routers.

This lives here rather than in `ebay_deletion.py`, where it started. That was
the right home while the compliance endpoint was the whole application; it
stopped being right the moment a second router existed, because it made one
feature's module responsible for assembling every other one.

Configuration is injected so tests never touch the environment.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from book_watch.abebooks import Reader
from book_watch.config import DeletionEndpointConfig, load_deletion_config
from book_watch.enrichment import EnrichFn
from book_watch.web import design, ebay_deletion, listings, manifest, version, wantlist
from book_watch.web.page_lines import PageLines
from book_watch.web.searching import SearchFn

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    config: DeletionEndpointConfig | None = None,
    read_abebooks: Reader | None = None,
    *,
    search: SearchFn | None = None,
    enrich: EnrichFn | None = None,
) -> FastAPI:
    """Build the application.

    The deletion config is loaded eagerly, so a missing or malformed token
    fails at startup with a clear message rather than at the moment eBay
    validates the endpoint.

    eBay's *search* credentials are deliberately not loaded here — see
    `listings.LazyBrowseSearch`. Production holds the deletion secrets and not
    the search keys, and the compliance endpoint must boot without them.

    AbeBooks is read only when a reader is passed, which only the production
    entry point does, so nothing that builds the app for a test reads it.

    `search` and `enrich` default to the real eBay and Open Library clients.
    `scripts/serve_local.py` passes fakes, so the app runs locally without
    making a request.
    """
    app = FastAPI(
        title="book-watch",
        description="Personal used-book want-list watcher.",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(ebay_deletion.build_router(config or load_deletion_config()))
    app.include_router(
        listings.build_router(search, enrich=enrich, read_abebooks=read_abebooks)
    )
    app.include_router(
        wantlist.build_router(search=search, enrich=enrich, read_abebooks=read_abebooks)
    )
    app.include_router(design.build_router())
    app.include_router(manifest.build_router())
    app.include_router(version.build_router())
    # htmx is vendored rather than loaded from a CDN: one file, no runtime
    # dependency on somebody else's uptime, and it works offline.
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.add_middleware(PageLines)
    return app

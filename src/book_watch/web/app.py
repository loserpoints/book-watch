"""Builds the application out of its routers.

This lives here rather than in `ebay_deletion.py`, where it started. That was
the right home while the compliance endpoint was the whole application; it
stopped being right the moment a second router existed, because it made one
feature's module responsible for assembling every other one.

Configuration is injected so tests never touch the environment.
"""

from __future__ import annotations

from fastapi import FastAPI

from book_watch.config import DeletionEndpointConfig, load_deletion_config
from book_watch.web import ebay_deletion, listings


def create_app(config: DeletionEndpointConfig | None = None) -> FastAPI:
    """Build the application.

    The deletion config is loaded eagerly, so a missing or malformed token
    fails at startup with a clear message rather than at the moment eBay
    validates the endpoint.

    eBay's *search* credentials are deliberately not loaded here — see
    `listings.LazyBrowseSearch`. Production holds the deletion secrets and not
    the search keys, and the compliance endpoint must boot without them.
    """
    app = FastAPI(
        title="book-watch",
        description="Personal used-book want-list watcher.",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(ebay_deletion.build_router(config or load_deletion_config()))
    app.include_router(listings.build_router())
    return app

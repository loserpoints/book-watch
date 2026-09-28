"""The web app manifest: what makes bookwatch install like an app (S35, #99).

A phone that adds the site to its home screen reads this for the name under
the icon, the icons, and to open in a window of its own ("standalone")
rather than a browser tab. Its colours come from the tokens, so the splash
and the status bar are the app's own and cannot drift from them.

**No service worker**, deliberately. A worker that caches pages is the
easiest way to serve yesterday's copies as today's, which is the failure
decision 48 fixed; offline behaviour deserves its own slice (decision 59).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from book_watch.web import tokens

MANIFEST_PATH = "/manifest.webmanifest"

#: The name under the icon. Alan's call, "for now" (S35).
NAME = "bookwatch"

ICONS = [
    {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
    {
        "src": "/static/icons/icon-maskable-512.png",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]


def manifest() -> dict:
    return {
        "id": "/",
        "name": NAME,
        "short_name": NAME,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        # Dark first (principle 8): the splash and status bar are the page's
        # own background, the same colour the theme-color meta already uses.
        "background_color": tokens.colour("bg"),
        "theme_color": tokens.colour("bg"),
        "icons": ICONS,
    }


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get(MANIFEST_PATH, include_in_schema=False)
    def serve() -> JSONResponse:
        return JSONResponse(manifest(), media_type="application/manifest+json")

    return router

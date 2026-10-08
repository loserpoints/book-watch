"""Which version of the app is running, for a page left open to ask (S75, #256).

The server draws every piece of screen, so after a deploy only the new
version can draw anything. A page asks this whenever it becomes visible
again, and reloads in full when the answer isn't the version that drew it.
Never cached: a stale answer would hide the deploy it exists to report.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from book_watch.web.assets import app_version

VERSION_PATH = "/version"


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get(VERSION_PATH, response_class=PlainTextResponse)
    def version() -> PlainTextResponse:
        return PlainTextResponse(app_version(), headers={"Cache-Control": "no-store"})

    return router

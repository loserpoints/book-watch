"""One `page` line per request to the app, in place of uvicorn's own.

Plain ASGI rather than Starlette's `BaseHTTPMiddleware`, so the line is written
once the response has been sent, and a background task the request started,
such as examining copies, runs after it rather than inside its time.
"""

from __future__ import annotations

import time
from typing import Any

from book_watch import monitoring

#: Fly calls it every 30 seconds. A line each would be 2,900 a day of nothing.
QUIET = frozenset({"/health"})


class PageLines:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["path"] in QUIET:
            await self.app(scope, receive, send)
            return
        started = time.monotonic()
        status = 500
        written = False

        def write() -> None:
            nonlocal written
            if not written:
                written = True
                ms = round((time.monotonic() - started) * 1000)
                monitoring.page(scope["path"], status, ms)

        async def sending(message: Any) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                write()

        try:
            await self.app(scope, receive, sending)
        finally:
            write()

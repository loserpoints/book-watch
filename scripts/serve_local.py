"""Serve the app locally for screenshots, unable to make a single request.

    uv run python scripts/serve_local.py book-watch.db [port]

This environment holds real eBay keys, so the app as built for production
searches eBay when a book page opens and then examines every copy it finds,
spending eBay and Open Library requests on a throwaway database. That happened
in M13 and again in M14 despite a written rule, so this makes it impossible:
eBay's search returns nothing, examining copies does nothing, AbeBooks is never
read, and any request that still tries to leave is refused with an error.
Seed the database with the copies a screenshot needs.
"""

from __future__ import annotations

import os
import sys

import httpx
from fastapi import FastAPI

from book_watch.config import DeletionEndpointConfig
from book_watch.ebay.search import Results
from book_watch.web.app import create_app


class RefusedRequest(httpx.ConnectError):
    """A request the local app tried to make. A connection error, so the app
    handles it as it would being offline: a cover shows its placeholder."""


def block_network() -> None:
    """Refuse every real HTTP request from this process."""

    def refuse(self, outgoing, *args, **kwargs):
        raise RefusedRequest(
            f"serve_local makes no requests: {outgoing.url}", request=outgoing
        )

    httpx.HTTPTransport.handle_request = refuse  # type: ignore[method-assign]


def app() -> FastAPI:
    block_network()
    return create_app(
        DeletionEndpointConfig("x" * 40, "https://local.invalid/ebay/deletion"),
        read_abebooks=None,
        search=lambda query, limit, **_: Results([], total=0),
        enrich=lambda work_id: None,
    )


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    os.environ["BOOK_WATCH_DB_PATH"] = argv[0]
    import uvicorn

    from book_watch import monitoring

    # The lines as production writes them, with uvicorn told not to set up
    # its own logging over them.
    monitoring.configure()
    uvicorn.run(
        app(),
        host="127.0.0.1",
        port=int(argv[1]) if len(argv) > 1 else 8000,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

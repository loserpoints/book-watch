"""Wiring for the one thing every screen that shows copies needs.

Apart from any one router because two screens search now: the book page opens
a book, and the want-list walks the whole shelf. Leaving this in whichever
module happened to need it first is how the want-list's endpoints ended up
living in the book page's module.

The search function is injected everywhere it is used, so a page can be tested
without a network, a key, or eBay being up — and so a test cannot reach eBay
by forgetting to pass a stub.
"""

from __future__ import annotations

from collections.abc import Callable

from book_watch.config import load_ebay_credentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.search import BrowseClient, Listing, Scope

#: Takes a query and a limit, returns listings. `BrowseClient.search` is the
#: real one; tests pass a function that returns whatever they need. `scope` is
#: keyword-only and defaulted, so the ad-hoc search route — which has no scope
#: of its own — can ignore it.
SearchFn = Callable[..., list[Listing]]


class LazyBrowseSearch:
    """Builds the eBay client on first search rather than at startup.

    This laziness is load-bearing, not tidiness. Fly holds the deletion
    endpoint's secrets and *not* the eBay keys, so an application that read
    `EBAY_CLIENT_ID` while booting would fail to start in production. That
    endpoint carries an uptime obligation which has nothing to do with the
    rest of the app — eBay re-validates it on its own schedule and disables
    the keyset when the check fails (decisions.md entry 16).

    So a missing key breaks searching, loudly, and breaks nothing else.
    """

    def __init__(self) -> None:
        self._browse: BrowseClient | None = None

    def __call__(self, query: str, limit: int, *, scope: Scope = "us") -> list[Listing]:
        if self._browse is None:
            tokens = EbayTokenProvider(load_ebay_credentials())
            self._browse = BrowseClient(tokens)
        return self._browse.search(query, limit=limit, scope=scope)

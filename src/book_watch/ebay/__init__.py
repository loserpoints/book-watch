"""Client for the eBay Browse API, the anchor listing source.

It is free, allows 5,000 calls a day, and prices shipping per copy.

`search` is deliberately not re-exported here. It is runnable as
`python -m book_watch.ebay.search`, and importing it into the package would
make Python load it twice on that command — once for the package, once as
`__main__` — which it warns about and which would give the module two
identities. Import from `book_watch.ebay.search` directly.
"""

from book_watch.ebay.auth import AccessToken, EbayTokenProvider
from book_watch.ebay.errors import EbayAuthError, EbayError, EbaySearchError

__all__ = [
    "AccessToken",
    "EbayAuthError",
    "EbayError",
    "EbaySearchError",
    "EbayTokenProvider",
]

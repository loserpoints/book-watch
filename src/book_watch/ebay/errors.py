"""Exceptions raised by the eBay client."""

from __future__ import annotations


class EbayError(Exception):
    """Anything that went wrong talking to eBay."""


class EbayAuthError(EbayError):
    """The token exchange failed, or returned something unusable.

    Covers rejected credentials, an unreachable endpoint and a malformed
    response alike. Callers that only want to answer "can we talk to eBay?"
    do not need to tell those apart.
    """

"""Verify the eBay credentials work: `uv run python -m book_watch.ebay`.

Makes exactly one request — a token exchange — and reports what came back.
It never prints the token. A credential in terminal scrollback is a credential
you no longer control.
"""

from __future__ import annotations

import sys

from book_watch.config import MissingCredentialError, load_ebay_credentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.errors import EbayAuthError

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_NOT_CONFIGURED = 2


def main() -> int:
    try:
        credentials = load_ebay_credentials()
    except MissingCredentialError as exc:
        print(f"Not configured: {exc}", file=sys.stderr)
        return EXIT_NOT_CONFIGURED

    try:
        with EbayTokenProvider(credentials) as provider:
            token = provider.token()
    except EbayAuthError as exc:
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        for line in _hints(str(exc), credentials.client_id):
            print(f"  - {line}", file=sys.stderr)
        return EXIT_REJECTED

    print("eBay credentials are valid.")
    print(f"  token type   {token.token_type}")
    print(f"  scope        {token.scope}")
    print(f"  valid for    {round(token.lifetime_seconds / 60)} minutes")
    print(f"  token        {len(token.value)} characters (not shown)")
    return EXIT_OK


def _hints(message: str, client_id: str) -> list[str]:
    """Suggest what to check, for the one failure that gives no clue by itself.

    `invalid_client` is eBay's answer to every credential problem, so the
    error alone never says which one it is. These are the four causes worth
    ruling out, cheapest first. Nothing here prints any credential material.
    """
    if "invalid_client" not in message:
        return []
    hints = [
        "The secret must be the keyset's Cert ID, not the Dev ID.",
        "A regenerated keyset invalidates the old secret — recopy both values.",
        "A keyset stays disabled until the API License Agreement is accepted.",
    ]
    if "SBX" in client_id.upper():
        hints.insert(
            0,
            "This client ID looks like a sandbox keyset, and this check talks "
            "to production. Sandbox keys only work against api.sandbox.ebay.com.",
        )
    return hints


if __name__ == "__main__":
    raise SystemExit(main())

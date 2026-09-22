"""OAuth client-credentials flow for the eBay Browse API.

eBay issues an *application* access token — it identifies this app, not a user,
which is all a read-only search needs. The token is valid for two hours, so
this module mints one and holds it rather than exchanging credentials per
request. That matters for more than latency: the daily call budget is finite
(decisions.md entry 4), and spending it on authentication would be a waste of
the headroom the choice of API was justified by.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from book_watch.config import EbayCredentials
from book_watch.ebay.errors import EbayAuthError

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

#: The only scope a public search needs. Buying and selling scopes require a
#: user token, which this tool will never ask for — it links out, it does not
#: transact.
PUBLIC_DATA_SCOPE = "https://api.ebay.com/oauth/api_scope"

#: Treat a token as expired this long before it really is, so a request started
#: near the boundary does not arrive with a token that died in flight.
EXPIRY_MARGIN_SECONDS = 300.0

DEFAULT_TIMEOUT_SECONDS = 15.0

#: Services are entitled to know who is calling them. See CLAUDE.md.
USER_AGENT = (
    "book-watch/0.1 (personal book want-list tool; "
    "+https://github.com/loserpoints/book-watch)"
)

_Clock = Callable[[], float]


@dataclass(frozen=True, slots=True, repr=False)
class AccessToken:
    """A token and the facts about it worth reporting.

    As with `EbayCredentials`, the repr hides the value: this object is the
    single most sensitive thing in the process, and it should not leak into a
    traceback.
    """

    value: str
    token_type: str
    scope: str
    lifetime_seconds: float
    expires_at: float

    def __repr__(self) -> str:
        return (
            f"AccessToken(value=<hidden, {len(self.value)} chars>, "
            f"token_type={self.token_type!r}, scope={self.scope!r})"
        )

    def is_fresh(self, now: float, margin: float = EXPIRY_MARGIN_SECONDS) -> bool:
        return now + margin < self.expires_at


class EbayTokenProvider:
    """Mints eBay application tokens and reuses them until they near expiry.

    Not thread-safe: two threads racing on a cold cache would each mint a
    token. Harmless — eBay issues both — but wasteful. The scheduler this will
    sit behind runs one job at a time (decisions.md entry 8), so a lock would
    be machinery for a problem this app does not have. Revisit if that changes.
    """

    def __init__(
        self,
        credentials: EbayCredentials,
        *,
        client: httpx.Client | None = None,
        scope: str = PUBLIC_DATA_SCOPE,
        clock: _Clock = time.monotonic,
    ) -> None:
        self._credentials = credentials
        self._scope = scope
        # Monotonic rather than wall-clock: this measures a duration, and a
        # system clock adjustment should not make a live token look expired.
        self._clock = clock
        if client is None:
            client = httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
            self._owns_client = True
        else:
            self._owns_client = False
        self._client = client
        self._cached: AccessToken | None = None

    def token(self) -> AccessToken:
        """Return a usable token, minting a new one only when needed."""
        cached = self._cached
        if cached is not None and cached.is_fresh(self._clock()):
            return cached
        fresh = self._fetch()
        self._cached = fresh
        return fresh

    def _fetch(self) -> AccessToken:
        headers = {
            "Authorization": f"Basic {self._basic_auth()}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        form = {"grant_type": "client_credentials", "scope": self._scope}
        requested_at = self._clock()
        try:
            response = self._client.post(TOKEN_URL, headers=headers, data=form)
        except httpx.HTTPError as exc:
            raise EbayAuthError(
                f"Could not reach the eBay token endpoint: {exc}"
            ) from exc

        if response.status_code != httpx.codes.OK:
            raise EbayAuthError(_describe_failure(response))

        return _parse_token(response, requested_at=requested_at)

    def _basic_auth(self) -> str:
        pair = f"{self._credentials.client_id}:{self._credentials.client_secret}"
        return base64.b64encode(pair.encode("utf-8")).decode("ascii")

    def close(self) -> None:
        """Close the HTTP client, but only if this object created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> EbayTokenProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _parse_token(response: httpx.Response, *, requested_at: float) -> AccessToken:
    payload = _decode_json(response)

    value = payload.get("access_token")
    if not isinstance(value, str) or not value:
        raise EbayAuthError(
            "The eBay token response contained no access_token. "
            f"Keys present: {sorted(payload)}"
        )

    lifetime = payload.get("expires_in")
    if not isinstance(lifetime, int | float) or isinstance(lifetime, bool):
        raise EbayAuthError(
            f"The eBay token response had a non-numeric expires_in: {lifetime!r}"
        )

    return AccessToken(
        value=value,
        token_type=str(payload.get("token_type", "Application Access Token")),
        # eBay echoes the granted scope, but has been known to omit it. Falling
        # back to what was asked for keeps the reporting honest either way.
        scope=str(payload.get("scope") or PUBLIC_DATA_SCOPE),
        lifetime_seconds=float(lifetime),
        expires_at=requested_at + float(lifetime),
    )


def _decode_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise EbayAuthError(
            f"The eBay token endpoint returned unreadable JSON: {_excerpt(response)}"
        ) from exc
    if not isinstance(payload, dict):
        raise EbayAuthError(
            "Expected a JSON object from the eBay token endpoint, got "
            f"{type(payload).__name__}"
        )
    return payload


def _describe_failure(response: httpx.Response) -> str:
    """Turn an error response into one line worth reading.

    eBay answers a bad key with `{"error": "invalid_client", ...}`. Surfacing
    that beats a bare 401, because "invalid_client" and "invalid_scope" send
    you to different places.
    """
    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        code = payload.get("error")
        description = payload.get("error_description")
        detail = " ".join(str(part) for part in (code, description) if part)
    return (
        f"HTTP {response.status_code} from the eBay token endpoint"
        f"{': ' + detail if detail else f' ({_excerpt(response)})'}"
    )


def _excerpt(response: httpx.Response, limit: int = 200) -> str:
    body = response.text.strip().replace("\n", " ")
    return body[:limit] + "…" if len(body) > limit else body

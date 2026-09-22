"""Tests for the eBay token exchange.

Everything here but the final test runs against `httpx.MockTransport` — a fake
transport the client talks to instead of a socket. No network, no keys, so CI
needs neither.
"""

import base64

import httpx
import pytest

from book_watch.config import EbayCredentials
from book_watch.ebay.auth import (
    EXPIRY_MARGIN_SECONDS,
    PUBLIC_DATA_SCOPE,
    TOKEN_URL,
    USER_AGENT,
    EbayTokenProvider,
)
from book_watch.ebay.errors import EbayAuthError

CREDENTIALS = EbayCredentials(client_id="an-app-id", client_secret="a-cert-id")


class FakeClock:
    """A clock that only moves when a test moves it."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def token_response(
    *, access_token: str = "v^1.1#i^1#fake", expires_in: int = 7200
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": access_token,
            "expires_in": expires_in,
            "token_type": "Application Access Token",
            "scope": PUBLIC_DATA_SCOPE,
        },
    )


def build_provider(handler, clock=None) -> EbayTokenProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return EbayTokenProvider(CREDENTIALS, client=client, clock=clock or FakeClock())


def test_exchanges_the_credentials_for_a_token():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return token_response()

    token = build_provider(handler).token()

    assert token.value == "v^1.1#i^1#fake"
    assert token.scope == PUBLIC_DATA_SCOPE
    assert token.lifetime_seconds == 7200

    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == TOKEN_URL
    assert request.headers["User-Agent"] == USER_AGENT
    expected = base64.b64encode(b"an-app-id:a-cert-id").decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    body = request.content.decode()
    assert "grant_type=client_credentials" in body
    assert "scope=" in body


def test_a_live_token_is_reused_rather_than_reminted():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return token_response()

    provider = build_provider(handler)

    assert provider.token() is provider.token()
    assert calls == 1


def test_a_token_near_expiry_is_replaced():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return token_response(access_token=f"token-{calls}")

    clock = FakeClock()
    provider = build_provider(handler, clock=clock)

    first = provider.token()
    # Still inside the safety margin, so still good.
    clock.advance(7200 - EXPIRY_MARGIN_SECONDS - 1)
    assert provider.token() is first
    # Now past it.
    clock.advance(2)
    assert provider.token().value == "token-2"
    assert calls == 2


def test_rejected_credentials_raise_and_say_why():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": "invalid_client",
                "error_description": "client authentication failed",
            },
        )

    with pytest.raises(EbayAuthError) as caught:
        build_provider(handler).token()

    message = str(caught.value)
    assert "401" in message
    assert "invalid_client" in message
    assert "a-cert-id" not in message


def test_an_html_error_page_is_reported_without_crashing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="<html>Service Unavailable</html>")

    with pytest.raises(EbayAuthError, match="503"):
        build_provider(handler).token()


def test_a_response_without_a_token_is_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"expires_in": 7200})

    with pytest.raises(EbayAuthError, match="no access_token"):
        build_provider(handler).token()


def test_a_non_numeric_expiry_is_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "t", "expires_in": "soon"})

    with pytest.raises(EbayAuthError, match="expires_in"):
        build_provider(handler).token()


def test_an_unreachable_endpoint_is_an_auth_error_too():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(EbayAuthError, match="Could not reach"):
        build_provider(handler).token()


def test_repr_hides_the_token_value():
    token = build_provider(lambda request: token_response()).token()

    assert "v^1.1#i^1#fake" not in repr(token)


@pytest.mark.network
def test_real_credentials_are_accepted_by_ebay():
    """One real token exchange. Run with `uv run pytest -m network`.

    Deselected by default so CI never needs a key and never depends on eBay
    being up. This is the test that catches a revoked or expired credential,
    which the mocked tests structurally cannot.
    """
    from book_watch.config import load_ebay_credentials

    with EbayTokenProvider(load_ebay_credentials()) as provider:
        token = provider.token()

    assert token.value
    assert token.lifetime_seconds > 0

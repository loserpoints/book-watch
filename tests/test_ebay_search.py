"""Tests for the eBay Browse search client.

Everything here but the final test runs against `httpx.MockTransport`, so CI
needs no key and does not depend on eBay being up. See docs/decisions.md
entries 13 and 15.
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from book_watch.config import EbayCredentials
from book_watch.ebay.auth import PUBLIC_DATA_SCOPE, USER_AGENT, EbayTokenProvider
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import (
    DEFAULT_MARKETPLACE_ID,
    MAX_LIMIT,
    SEARCH_URL,
    BrowseClient,
    Money,
)

CREDENTIALS = EbayCredentials(client_id="an-app-id", client_secret="a-cert-id")


def token_provider() -> EbayTokenProvider:
    """A provider wired to a fake token endpoint, so no real key is needed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "fake-token",
                "expires_in": 7200,
                "token_type": "Application Access Token",
                "scope": PUBLIC_DATA_SCOPE,
            },
        )

    return EbayTokenProvider(
        CREDENTIALS, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def build_browse(handler) -> BrowseClient:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BrowseClient(token_provider(), client=client)


def search_response(*summaries) -> httpx.Response:
    return httpx.Response(
        200, json={"total": len(summaries), "itemSummaries": list(summaries)}
    )


def a_summary(**overrides):
    """A plausible `itemSummary`, in the shape eBay actually sends."""
    summary = {
        "itemId": "v1|123456789|0",
        "title": "Crash by J. G. Ballard",
        "price": {"value": "8.99", "currency": "USD"},
        "itemWebUrl": "https://www.ebay.com/itm/123456789",
        "condition": "Good",
        "conditionId": "5000",
        "image": {"imageUrl": "https://i.ebayimg.com/images/g/abc/s-l225.jpg"},
        "shippingOptions": [
            {"shippingCost": {"value": "3.99", "currency": "USD"}},
        ],
        "itemCreationDate": "2026-09-01T12:00:00.000Z",
    }
    summary.update(overrides)
    return summary


def responds_with(response: httpx.Response):
    return lambda request: response


def test_searches_by_keyword_and_sends_the_headers_ebay_requires():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response(a_summary())

    build_browse(handler).search("Ballard Crash", limit=10)

    (request,) = seen
    assert request.method == "GET"
    assert str(request.url).startswith(SEARCH_URL)
    assert request.url.params["q"] == "Ballard Crash"
    assert request.url.params["limit"] == "10"
    assert "gtin" not in request.url.params
    assert request.headers["Authorization"] == "Bearer fake-token"
    assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == DEFAULT_MARKETPLACE_ID
    assert request.headers["User-Agent"] == USER_AGENT


def test_searching_by_gtin_uses_the_gtin_parameter_instead_of_q():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response()

    build_browse(handler).search("9780099448396", search_by="gtin")

    (request,) = seen
    assert request.url.params["gtin"] == "9780099448396"
    assert "q" not in request.url.params


def test_parses_a_listing_into_the_fields_the_app_ranks_on():
    listings = build_browse(responds_with(search_response(a_summary()))).search("x")

    (listing,) = listings
    assert listing.item_id == "v1|123456789|0"
    assert listing.title == "Crash by J. G. Ballard"
    assert listing.condition == "Good"
    assert listing.condition_id == "5000"
    assert listing.price == Money(Decimal("8.99"), "USD")
    assert listing.shipping_cost == Money(Decimal("3.99"), "USD")
    assert listing.landed_cost == Money(Decimal("12.98"), "USD")
    assert listing.thumbnail_url.endswith("s-l225.jpg")
    assert listing.item_web_url == "https://www.ebay.com/itm/123456789"
    assert listing.listing_date == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def test_prices_keep_their_exactness():
    """Decimal, not float. 0.1 + 0.2 must not turn up in a price."""
    summary = a_summary(
        price={"value": "0.10", "currency": "USD"},
        shippingOptions=[{"shippingCost": {"value": "0.20", "currency": "USD"}}],
    )
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.landed_cost.amount == Decimal("0.30")
    assert str(listing.landed_cost) == "0.30 USD"


def test_free_shipping_is_not_the_same_as_unstated_shipping():
    """The distinction the whole landed-cost ranking rests on."""
    free = a_summary(
        shippingOptions=[{"shippingCost": {"value": "0.00", "currency": "USD"}}]
    )
    unstated = a_summary(shippingOptions=[{"shippingCostType": "CALCULATED"}])

    listings = build_browse(responds_with(search_response(free, unstated))).search("x")
    ships_free, calculated = listings

    assert ships_free.shipping_cost == Money(Decimal("0.00"), "USD")
    assert ships_free.landed_cost == Money(Decimal("8.99"), "USD")

    assert calculated.shipping_cost is None
    assert calculated.landed_cost is None


def test_the_cheapest_shipping_option_is_the_one_that_counts():
    summary = a_summary(
        shippingOptions=[
            {"shippingCost": {"value": "9.99", "currency": "USD"}},
            {"shippingCost": {"value": "3.49", "currency": "USD"}},
            {"shippingCost": {"value": "6.00", "currency": "USD"}},
        ]
    )
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.shipping_cost == Money(Decimal("3.49"), "USD")


def test_shipping_in_another_currency_gives_no_landed_cost_rather_than_a_wrong_one():
    summary = a_summary(
        shippingOptions=[{"shippingCost": {"value": "3.00", "currency": "GBP"}}]
    )
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.shipping_cost == Money(Decimal("3.00"), "GBP")
    assert listing.landed_cost is None


def test_shipping_options_in_mixed_currencies_are_not_compared():
    summary = a_summary(
        shippingOptions=[
            {"shippingCost": {"value": "3.00", "currency": "GBP"}},
            {"shippingCost": {"value": "4.00", "currency": "USD"}},
        ]
    )
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.shipping_cost is None


def test_a_thumbnail_falls_back_to_thumbnail_images():
    summary = a_summary(
        image=None,
        thumbnailImages=[{"imageUrl": "https://i.ebayimg.com/images/g/xyz/s-l64.jpg"}],
    )
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.thumbnail_url.endswith("s-l64.jpg")


def test_a_listing_with_no_image_is_still_a_listing():
    summary = a_summary(image=None)
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.thumbnail_url is None


def test_an_unreadable_date_does_not_lose_the_listing():
    summary = a_summary(itemCreationDate="the day before yesterday")
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.listing_date is None
    assert listing.title


def test_no_matches_comes_back_as_an_empty_list():
    """eBay omits itemSummaries entirely rather than sending an empty list."""
    response = httpx.Response(200, json={"total": 0, "href": SEARCH_URL, "limit": 50})

    assert build_browse(responds_with(response)).search("nothing at all") == []


def test_a_listing_missing_its_id_is_an_error_not_a_silent_drop():
    summary = a_summary()
    del summary["itemId"]

    with pytest.raises(EbaySearchError, match="no usable itemId"):
        build_browse(responds_with(search_response(summary))).search("x")


def test_a_listing_missing_its_price_is_an_error():
    summary = a_summary()
    del summary["price"]

    with pytest.raises(EbaySearchError, match="no price object"):
        build_browse(responds_with(search_response(summary))).search("x")


def test_an_unreadable_price_is_an_error():
    summary = a_summary(price={"value": "about a fiver", "currency": "USD"})

    with pytest.raises(EbaySearchError, match="unreadable price"):
        build_browse(responds_with(search_response(summary))).search("x")


def test_an_api_error_reports_ebays_own_message():
    response = httpx.Response(
        400,
        json={
            "errors": [
                {"errorId": 12001, "message": "The 'q' or 'category_ids' is required."}
            ]
        },
    )

    with pytest.raises(EbaySearchError) as caught:
        build_browse(responds_with(response)).search("x")

    message = str(caught.value)
    assert "400" in message
    assert "12001" in message
    assert "is required" in message


def test_an_html_error_page_is_reported_without_crashing():
    response = httpx.Response(503, text="<html>Service Unavailable</html>")

    with pytest.raises(EbaySearchError, match="503"):
        build_browse(responds_with(response)).search("x")


def test_unreadable_json_is_an_error():
    response = httpx.Response(200, text="not json at all")

    with pytest.raises(EbaySearchError, match="unreadable JSON"):
        build_browse(responds_with(response)).search("x")


def test_an_unreachable_api_is_a_search_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(EbaySearchError, match="Could not reach"):
        build_browse(handler).search("x")


def test_an_empty_query_is_refused_before_a_request_is_made():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return search_response()

    with pytest.raises(EbaySearchError, match="non-empty"):
        build_browse(handler).search("   ")

    assert calls == 0


@pytest.mark.parametrize("limit", [0, -1, MAX_LIMIT + 1])
def test_an_out_of_range_limit_is_refused_before_a_request_is_made(limit):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return search_response()

    with pytest.raises(EbaySearchError, match="limit must be"):
        build_browse(handler).search("x", limit=limit)

    assert calls == 0


def test_a_passed_in_client_is_not_closed_by_the_browse_client():
    """Ownership matches EbayTokenProvider: you close what you created."""
    client = httpx.Client(transport=httpx.MockTransport(lambda r: search_response()))
    with BrowseClient(token_provider(), client=client):
        pass

    assert not client.is_closed


@pytest.mark.network
def test_a_real_search_returns_listings():
    """One real search. Run with `uv run pytest -m network`.

    Deselected by default. This is the test that catches eBay changing the
    response shape, which the mocked tests structurally cannot.
    """
    from book_watch.ebay.search import search_listings

    listings = search_listings("9780099448396", limit=5)

    assert listings, "expected at least one listing for a common paperback"
    first = listings[0]
    assert first.item_id and first.title
    assert first.price.amount >= 0
    assert first.item_web_url.startswith("https://")

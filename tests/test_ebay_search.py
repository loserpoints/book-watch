"""Tests for the eBay Browse search client.

Everything here but the final test runs against `httpx.MockTransport`, so CI
needs no key and does not depend on eBay being up.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from book_watch.config import EbayCredentials
from book_watch.ebay.auth import PUBLIC_DATA_SCOPE, USER_AGENT, EbayTokenProvider
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import (
    DEFAULT_MARKETPLACE_ID,
    END_USER_CONTEXT_HEADER,
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


def build_browse(handler, *, ship_to_zip: str | None = None) -> BrowseClient:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BrowseClient(token_provider(), client=client, ship_to_zip=ship_to_zip)


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
        "seller": {
            "username": "betterworldbooks",
            "feedbackPercentage": "98.9",
            "feedbackScore": 2_400_000,
        },
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


def test_a_ship_to_zip_is_sent_url_encoded():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response(a_summary())

    build_browse(handler, ship_to_zip="10001").search("Hey Jack", limit=10)

    (request,) = seen
    assert request.headers[END_USER_CONTEXT_HEADER] == (
        "contextualLocation=country%3DUS%2Czip%3D10001"
    )


def test_without_a_ship_to_zip_no_location_is_sent():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response(a_summary())

    build_browse(handler).search("Hey Jack", limit=10)

    (request,) = seen
    assert END_USER_CONTEXT_HEADER not in request.headers


RECORDED = json.loads(
    (Path(__file__).parent / "data" / "calculated_shipping.json").read_text()
)

#: The two Hey Jack! copies from #177, with calculated shipping.
HEY_JACK = {"v1|407056103912|0": "14.34", "v1|175371270006|0": "13.12"}


def parse_recorded(name: str) -> dict[str, Money | None]:
    listings = build_browse(responds_with(httpx.Response(200, json=RECORDED[name])))
    return {
        listing.item_id: listing.landed_cost
        for listing in listings.search("Hey Jack Barry Hannah")
    }


@pytest.mark.parametrize("name", ["without_location", "with_location_unencoded"])
def test_a_real_search_without_a_working_location_leaves_calculated_shipping_unpriced(
    name,
):
    landed = parse_recorded(name)

    assert len(landed) == 27
    assert all(landed[item_id] is None for item_id in HEY_JACK)
    assert sum(cost is None for cost in landed.values()) == 3


def test_a_real_search_with_a_location_prices_every_copy():
    landed = parse_recorded("with_location")

    assert len(landed) == 27
    assert all(cost is not None for cost in landed.values())
    for item_id, delivered in HEY_JACK.items():
        assert landed[item_id] == Money(Decimal(delivered), "USD")


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
    assert listing.seller == "betterworldbooks"
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


def test_a_listing_with_no_seller_is_still_a_listing():
    """A missing seller is odd, but the copy is still buyable."""
    summary = a_summary(seller=None)
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.seller is None
    assert listing.item_id


def test_only_the_seller_username_is_kept():
    """Feedback comes back in the same object and is deliberately dropped."""
    summary = a_summary(seller={"username": "a_bookshop", "feedbackPercentage": "12.0"})
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.seller == "a_bookshop"


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
    summary = a_summary(
        itemCreationDate="the day before yesterday", itemOriginDate="last spring"
    )
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
    assert first.seller, "eBay should name a seller on every real listing"
    assert first.price.amount >= 0
    assert first.item_web_url.startswith("https://")


class RecordingBrowse:
    """Stands in for BrowseClient, keeping the ZIP each search ran with."""

    searched_with: list[str | None] = []

    def __init__(self, tokens, *, ship_to_zip=None):
        self.ship_to_zip = ship_to_zip

    def search(self, query, *, limit, scope):
        RecordingBrowse.searched_with.append(self.ship_to_zip)
        return []


@pytest.fixture
def lazy_search(monkeypatch):
    """The app's search with a ZIP held in a list, as Settings holds it."""
    from book_watch.web import searching

    monkeypatch.setenv("EBAY_CLIENT_ID", "an-app-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "a-cert-id")
    monkeypatch.setattr("book_watch.config.load_dotenv", lambda: None)
    monkeypatch.setattr(searching, "BrowseClient", RecordingBrowse)
    RecordingBrowse.searched_with = []
    held: list[str | None] = [None]
    search = searching.LazyBrowseSearch(ship_to=lambda: held[0])
    return search, held


def test_each_search_reads_the_zip_settings_hold_when_it_runs(lazy_search, caplog):
    """S84 (#182): a ZIP changed in Settings applies from the next search."""
    search, held = lazy_search
    held[0] = "10001"
    search("Hey Jack", 50)
    held[0] = "60614"
    search("Hey Jack", 50)

    assert RecordingBrowse.searched_with == ["10001", "60614"]
    assert "10001" not in caplog.text and "60614" not in caplog.text
    assert "Shipping for calculated listings is off" not in caplog.text


def test_without_a_zip_the_app_searches_and_says_shipping_is_off_once(
    lazy_search, caplog
):
    search, _ = lazy_search

    assert search("Hey Jack", 50) == []
    search("Hey Jack", 50)

    assert RecordingBrowse.searched_with == [None, None]
    assert caplog.text.count("Shipping for calculated listings is off") == 1


def test_the_secret_is_read_nowhere():
    """S84 (#182): the ZIP moved to Settings, and the Fly secret went."""
    from pathlib import Path

    root = Path(__file__).parent.parent
    sources = [
        *root.glob("src/**/*.py"),
        *root.glob("scripts/*.py"),
        root / ".env.example",
    ]
    assert not [p for p in sources if "SHIP_TO_ZIP" in p.read_text()]


def test_a_raw_search_keeps_fields_the_app_does_not_read():
    """`search_raw` is the same request as `search`, with nothing dropped."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response(a_summary(somethingNew=["kept"]))

    with build_browse(handler) as browse:
        payload = browse.search_raw("Crash Ballard")
        browse.search("Crash Ballard")

    assert payload["itemSummaries"][0]["somethingNew"] == ["kept"]
    assert seen[0].url == seen[1].url


def test_a_raw_search_refuses_what_a_search_refuses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    with build_browse(handler) as browse, pytest.raises(EbaySearchError):
        browse.search_raw("Crash Ballard")


# --- how a copy is sold (S59) -------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "sent"),
    [
        ("us", "buyingOptions:{FIXED_PRICE},itemLocationCountry:US"),
        ("everywhere", "buyingOptions:{FIXED_PRICE}"),
    ],
)
def test_every_search_asks_for_fixed_price_listings_only(scope, sent):
    """An auction's price is its current bid, so auctions are never asked for."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return search_response(a_summary())

    build_browse(handler).search("Stoner John Williams", scope=scope)

    (request,) = seen
    assert request.url.params["filter"] == sent


def test_a_copy_that_takes_offers_says_so():
    """Shaped like the real Pride and Prejudice search in #211."""
    offers = a_summary(itemId="v1|1|0", buyingOptions=["FIXED_PRICE", "BEST_OFFER"])
    firm = a_summary(itemId="v1|2|0", buyingOptions=["FIXED_PRICE"])
    unstated = a_summary(itemId="v1|3|0")

    listings = build_browse(responds_with(search_response(offers, firm, unstated)))
    found = {listing.item_id: listing for listing in listings.search("Austen")}

    assert found["v1|1|0"].takes_offers
    assert not found["v1|2|0"].takes_offers
    assert found["v1|3|0"].buying_options == ()
    assert not found["v1|3|0"].takes_offers


# --- when a copy was listed (S62) --------------------------------------------


def test_a_relisted_copy_keeps_the_date_it_was_first_listed():
    """eBay: itemOriginDate "will be retained if an item is relisted", and
    itemCreationDate is when this listing was created."""
    relisted = a_summary(
        itemCreationDate="2026-09-30T10:00:00.000Z",
        itemOriginDate="2026-03-02T09:00:00.000Z",
    )
    (listing,) = build_browse(responds_with(search_response(relisted))).search("x")

    assert listing.listing_date == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)


def test_without_an_origin_date_the_creation_date_stands_in():
    summary = a_summary(itemCreationDate="2026-09-01T12:00:00.000Z")
    summary.pop("itemOriginDate", None)
    (listing,) = build_browse(responds_with(search_response(summary))).search("x")

    assert listing.listing_date == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

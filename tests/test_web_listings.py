"""Tests for the results page.

No network: the router takes its search function as an argument, so these
drive the real templates against listings the test made up.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch.config import DeletionEndpointConfig, MissingCredentialError
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import Listing, Money
from book_watch.web import listings as listings_module
from book_watch.web.app import create_app

DELETION_CONFIG = DeletionEndpointConfig(
    verification_token="a" * 32,
    endpoint_url="https://book-watch.fly.dev/ebay/deletion",
)


def a_listing(**overrides) -> Listing:
    fields = {
        "item_id": "v1|123|0",
        "title": "Crash by J. G. Ballard",
        "price": Money(Decimal("8.99"), "USD"),
        "item_web_url": "https://www.ebay.com/itm/123",
        "condition": "Good",
        "seller": "betterworldbooks",
        "shipping_cost": Money(Decimal("3.99"), "USD"),
        "thumbnail_url": "https://i.ebayimg.com/images/g/abc/s-l225.jpg",
        "listing_date": datetime(2026, 9, 1, tzinfo=UTC),
    }
    fields.update(overrides)
    return Listing(**fields)


def client_for(search) -> TestClient:
    app = FastAPI()
    app.include_router(listings_module.build_router(search))
    return TestClient(app)


def returning(*results):
    return lambda query, limit: list(results)


def test_a_listing_shows_everything_needed_to_judge_it_without_clicking():
    """J3's whole point: rule a copy out from the list, not from the listing."""
    page = client_for(returning(a_listing())).get("/search?isbn=9780099448396").text

    assert "Crash by J. G. Ballard" in page
    assert "Good" in page
    assert "betterworldbooks" in page
    assert "8.99 USD" in page
    assert "3.99 USD" in page
    assert "12.98 USD delivered" in page
    assert "https://i.ebayimg.com/images/g/abc/s-l225.jpg" in page
    assert "https://www.ebay.com/itm/123" in page


def test_unknown_shipping_is_shown_as_unknown_rather_than_as_a_total():
    """The three-valued rule from decision 22, carried through to the page."""
    listing = a_listing(shipping_cost=None)
    page = client_for(returning(listing)).get("/search?isbn=x").text

    assert "shipping calculated at checkout" in page
    assert "8.99 USD + shipping unknown" in page
    assert "delivered" not in page


def test_a_seller_cannot_inject_markup_through_a_title():
    """Titles are seller-written. Autoescaping is the only thing between a
    seller and a script tag on this page, so it is asserted, not assumed."""
    listing = a_listing(title="<script>alert('xss')</script>")
    page = client_for(returning(listing)).get("/search?isbn=x").text

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_no_results_says_so_rather_than_showing_an_empty_page():
    page = client_for(returning()).get("/search?isbn=x").text

    assert "Nothing listed right now" in page


def test_no_isbn_explains_itself_and_does_not_search():
    calls = []

    def search(query, limit):
        calls.append(query)
        return []

    response = client_for(search).get("/search")

    assert response.status_code == 200
    assert "/search?isbn=" in response.text
    assert calls == []


def test_a_blank_isbn_is_treated_as_no_isbn():
    calls = []

    def search(query, limit):
        calls.append(query)
        return []

    client_for(search).get("/search?isbn=%20%20")

    assert calls == []


def test_the_limit_reaches_the_search():
    seen = {}

    def search(query, limit):
        seen["query"] = query
        seen["limit"] = limit
        return []

    client_for(search).get("/search?isbn=9780099448396&limit=5")

    assert seen == {"query": "9780099448396", "limit": 5}


@pytest.mark.parametrize("limit", [0, 201])
def test_an_out_of_range_limit_is_rejected_before_ebay_is_asked(limit):
    calls = []

    def search(query, limit):
        calls.append(limit)
        return []

    response = client_for(search).get(f"/search?isbn=x&limit={limit}")

    assert response.status_code == 422
    assert calls == []


def test_an_ebay_failure_is_reported_on_the_page_as_a_bad_gateway():
    def search(query, limit):
        raise EbaySearchError("HTTP 503 from the eBay Browse API")

    response = client_for(search).get("/search?isbn=x")

    assert response.status_code == 502
    assert "eBay could not be searched" in response.text
    assert "503" in response.text


def test_missing_credentials_are_reported_as_a_configuration_problem():
    def search(query, limit):
        raise MissingCredentialError("EBAY_CLIENT_ID is not set.")

    response = client_for(search).get("/search?isbn=x")

    assert response.status_code == 500
    assert "eBay is not configured" in response.text


def test_the_app_does_not_read_ebay_credentials_at_startup(monkeypatch):
    """Load them eagerly and the deployed compliance endpoint stops booting.

    Production holds the deletion secrets and not the eBay keys, and that
    endpoint has an uptime obligation of its own (decision 16). This is the
    test that stops someone making the search client eager for tidiness.
    """

    def explode(*args, **kwargs):
        raise AssertionError("eBay credentials must not be read at startup")

    monkeypatch.setattr(listings_module, "load_ebay_credentials", explode)

    client = TestClient(create_app(DELETION_CONFIG))

    assert client.get("/health").status_code == 200


def test_searching_without_ebay_keys_fails_loudly_and_breaks_nothing_else(
    monkeypatch,
):
    def missing(*args, **kwargs):
        raise MissingCredentialError("EBAY_CLIENT_ID is not set.")

    monkeypatch.setattr(listings_module, "load_ebay_credentials", missing)
    client = TestClient(create_app(DELETION_CONFIG))

    assert client.get("/search?isbn=x").status_code == 500
    # The endpoint eBay actually depends on is untouched by that failure.
    assert client.get("/health").status_code == 200


def test_the_results_page_and_the_deletion_endpoint_share_one_app():
    client = TestClient(create_app(DELETION_CONFIG))

    assert client.get("/search").status_code == 200
    assert client.get("/ebay/deletion?challenge_code=abc").status_code == 200

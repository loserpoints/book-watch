"""Tests for the results page.

No network: the router takes its search function as an argument, so these
drive the real templates against listings the test made up.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import db
from book_watch.config import DeletionEndpointConfig, MissingCredentialError
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import Listing, Money
from book_watch.web import listings as listings_module
from book_watch.web import wantlist as web_wantlist
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


# --- One book on the want-list, and what is for sale for it -----------------


@pytest.fixture
def book_client(tmp_path):
    """A client whose want-list is real and whose eBay is not."""
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    def make(search):
        app = FastAPI()
        app.include_router(listings_module.build_router(search, connect))
        app.include_router(web_wantlist.build_router(connect))
        return TestClient(app)

    return make


def add_book(client, isbn, title=""):
    client.post("/books", data={"isbn": isbn, "title": title, "override": "1"})


def test_a_book_on_the_list_shows_what_is_for_sale(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1")

    assert page.status_code == 200
    assert "Crash" in page.text
    assert "12.98 USD delivered" in page.text
    assert "https://www.ebay.com/itm/123" in page.text


def test_the_book_page_searches_for_that_book(book_client):
    seen = {}

    def search(query, limit):
        seen["query"] = query
        return []

    client = book_client(search)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")

    assert seen["query"] == "9780099448396"


def test_the_page_says_when_it_fetched(book_client):
    """So live data is never mistaken for stored data.

    The ad-hoc search is always live and says "fetched". The book page reads
    the store and says when the store was filled, which after S12 is a
    different claim and deserves a different word.
    """
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    assert (
        "fetched 20" in book_client(returning(a_listing())).get("/search?isbn=x").text
    )
    assert "checked 20" in client.get("/book/1").text


# --- the page reads the store ----------------------------------------------


def test_a_second_view_does_not_search_ebay_again(book_client):
    """Decision 30 as amended. Measured: one search is 1.8 seconds."""
    searches = []

    def search(query, limit):
        searches.append(query)
        return [a_listing()]

    client = book_client(search)
    add_book(client, "9780099448396", "Crash")

    client.get("/book/1")
    client.get("/book/1")
    client.get("/book/1")

    assert len(searches) == 1


def test_looking_again_searches_again(book_client):
    searches = []

    def search(query, limit):
        searches.append(query)
        return [a_listing()]

    client = book_client(search)
    add_book(client, "9780099448396", "Crash")

    client.get("/book/1")
    client.get("/book/1?refresh=1")

    assert len(searches) == 2


def test_a_copy_that_has_stopped_appearing_stops_being_shown(book_client):
    """It was sold or withdrawn. Keeping it would make this a list of things
    that used to be buyable."""
    listings = [a_listing()]
    client = book_client(lambda query, limit: list(listings))
    add_book(client, "9780099448396", "Crash")
    assert "https://www.ebay.com/itm/123" in client.get("/book/1").text

    listings.clear()

    assert "https://www.ebay.com/itm/123" not in client.get("/book/1?refresh=1").text


def test_the_page_never_fetches_a_listings_details(book_client):
    """Measured at 0.51s each: fifty of them is twenty-five seconds.

    There is no detail client wired to this router at all, so the assertion is
    that the page renders without one — if it ever needs one, this fails by
    raising rather than by being slow.
    """
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    assert client.get("/book/1").status_code == 200


def test_copies_nobody_has_examined_yet_are_said_to_be_unexamined(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    assert "Still digging" in page
    # The short version has to say the fact by itself: `title` does not
    # survive a touchscreen, so what hover adds is context, never the news.
    assert "not looked at closely yet" in page
    assert 'title="A copy has to declare its ISBN' in page


def test_a_copy_only_the_title_matches_goes_below_the_fold(book_client):
    """Text alone never reaches certain. Decision 33: 36% precision on the
    edition question, 12% on one book."""
    client = book_client(returning(a_listing(title="Crash by J. G. Ballard")))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    assert "might be this book" in page


def test_an_empty_result_says_when_it_checked(book_client):
    client = book_client(returning())
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    assert "Nothing listed right now" in page
    assert "checked 20" in page


def test_a_book_that_is_not_on_the_list_is_a_404(book_client):
    client = book_client(returning())

    page = client.get("/book/999")

    assert page.status_code == 404
    assert "not on the want-list" in page.text


def test_an_overridden_entry_warns_that_it_is_not_an_isbn(book_client):
    """Otherwise "nothing listed" reads as a fact about the market rather
    than a consequence of searching eBay for a sentence."""
    client = book_client(returning())
    add_book(client, "The Riddle of the Sands")

    page = client.get("/book/1").text

    assert "not an ISBN" in page
    assert "Expect worse matches" in page


def test_a_real_isbn_carries_no_such_warning(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    assert "not an ISBN" not in client.get("/book/1").text


def test_the_want_list_links_to_each_book(book_client):
    client = book_client(returning())
    add_book(client, "9780099448396", "Crash")

    assert 'href="/book/1"' in client.get("/").text


def test_an_ebay_failure_on_a_book_page_is_still_a_bad_gateway(book_client):
    def search(query, limit):
        raise EbaySearchError("HTTP 503 from the eBay Browse API")

    client = book_client(search)
    add_book(client, "9780099448396", "Crash")

    assert client.get("/book/1").status_code == 502

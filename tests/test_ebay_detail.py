"""Tests for what a seller declared, and for asking eBay once.

Recorded from real `getItem` responses during S6, trimmed to the fields this
app reads. `tests/conftest.py` makes a real request a loud failure, so nothing
here reaches eBay unless it says so.
"""

import httpx
import pytest

from book_watch import db
from book_watch.config import EbayCredentials
from book_watch.ebay.auth import EbayTokenProvider
from book_watch.ebay.declarations import Declarations
from book_watch.ebay.detail import Declared, ItemDetailClient, declared_isbn
from book_watch.ebay.errors import EbaySearchError

CREDENTIALS = EbayCredentials(client_id="an-app-id", client_secret="a-cert-id")

STONER_ITEM = {
    "itemId": "v1|123456789|0",
    "categoryPath": "Books & Magazines|Books",
    "localizedAspects": [
        {"type": "STRING", "name": "Book Title", "value": "Stoner"},
        {"type": "STRING", "name": "Author", "value": "John Williams"},
        {"type": "STRING", "name": "Format", "value": "Trade Paperback"},
        {
            "type": "STRING",
            "name": "Publisher",
            "value": "New York Review of Books, Incorporated, T.H.E.",
        },
        {"type": "STRING", "name": "Publication Year", "value": "2006"},
        {"type": "STRING", "name": "ISBN", "value": "9781590171998"},
    ],
}

#: A listing with no aspects at all. Roughly half of one book's listings in
#: the measured sample declared no number.
BARE_ITEM = {"itemId": "v1|987654321|0", "categoryPath": "Books"}


def token_provider() -> EbayTokenProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "a-token",
                "token_type": "Application Access Token",
                "expires_in": 7200,
            },
        )

    return EbayTokenProvider(
        CREDENTIALS, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def build_client(handler) -> ItemDetailClient:
    return ItemDetailClient(
        token_provider(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def responds_with(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


# --- reading what a seller said ---------------------------------------------


def test_a_listings_aspects_become_what_it_declares():
    declared = build_client(responds_with(STONER_ITEM)).declared_by("v1|123456789|0")

    assert declared.isbn == "9781590171998"
    assert declared.format == "Trade Paperback"
    assert declared.published == "2006"
    assert declared.category == "Books"


def test_a_listing_with_no_aspects_declares_nothing_rather_than_failing():
    declared = build_client(responds_with(BARE_ITEM)).declared_by("v1|987654321|0")

    assert declared.isbn is None
    assert declared.format is None


def test_an_item_that_has_gone_is_not_an_error():
    """It was a real listing a moment ago. No longer buyable is not a failure."""
    declared = build_client(responds_with({}, 404)).declared_by("v1|111|0")

    assert declared == Declared(item_id="v1|111|0", present=False)
    assert not declared.present, (
        "A 404 has to stay distinguishable from a live listing whose seller "
        "declared nothing. Re-asking overwrites the second and must not touch "
        "the first."
    )


def test_an_ebay_failure_is_an_error():
    with pytest.raises(EbaySearchError):
        build_client(responds_with({"errors": []}, 500)).declared_by("v1|111|0")


def test_the_item_id_survives_the_url():
    """eBay's ids contain pipes, which have to reach them intact."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=STONER_ITEM)

    build_client(handler).declared_by("v1|123456789|0")

    assert seen[0].endswith("/item/v1%7C123456789%7C0")


# --- finding the number a seller typed --------------------------------------


def test_an_isbn_10_becomes_the_isbn_13_of_the_same_edition():
    assert declared_isbn({"ISBN-10": "1590171993"}) == "9781590171998"


def test_an_ean_on_a_book_is_an_isbn():
    assert declared_isbn({"EAN": "9781590171998"}) == "9781590171998"


def test_several_numbers_in_one_field_take_the_first_that_parses():
    """Sellers list a hardcover's number beside a paperback's."""
    assert declared_isbn({"ISBN": "9781590171998, 9780099448396"}) == "9781590171998"


def test_a_field_of_nonsense_declares_no_number():
    assert declared_isbn({"ISBN": "see photos"}) is None


def test_no_number_field_at_all_declares_no_number():
    assert declared_isbn({"Format": "Paperback"}) is None


# --- asking once ------------------------------------------------------------


@pytest.fixture
def database(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


class CountingDetail:
    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def declared_by(self, item_id):
        self.asked.append(item_id)
        return self.answers[item_id]


def test_a_listing_is_asked_about_once_and_then_never_again(database):
    """Decision 33: the per-listing call is affordable only on this basis."""
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", isbn="9781590171998")})
    declarations = Declarations(database, detail)

    first = declarations.of("v1|1|0")
    second = declarations.of("v1|1|0")

    assert first == second
    assert detail.asked == ["v1|1|0"]


def test_a_listing_that_declared_nothing_is_still_only_asked_once(database):
    """Otherwise every page view re-asks about every silent listing."""
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0")})
    declarations = Declarations(database, detail)

    declarations.of("v1|1|0")
    declarations.of("v1|1|0")

    assert detail.asked == ["v1|1|0"]


def test_what_a_listing_declared_survives_a_restart(database, tmp_path):
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0", format="Hardcover")})
    Declarations(database, detail).of("v1|1|0")
    database.commit()

    reopened = db.connect(tmp_path / "book-watch.db")
    try:
        again = Declarations(reopened, detail).of("v1|1|0")
    finally:
        reopened.close()

    assert again.format == "Hardcover"
    assert detail.asked == ["v1|1|0"]


def test_knowing_what_a_page_will_cost_before_spending_it(database):
    detail = CountingDetail({"v1|1|0": Declared("v1|1|0")})
    declarations = Declarations(database, detail)
    declarations.of("v1|1|0")

    assert declarations.unasked(["v1|1|0", "v1|2|0", "v1|3|0"]) == ["v1|2|0", "v1|3|0"]
    assert declarations.unasked([]) == []


def test_asking_about_nothing_costs_nothing(database):
    detail = CountingDetail({})

    assert Declarations(database, detail).unasked([]) == []
    assert detail.asked == []


@pytest.mark.network
def test_a_real_item_comes_back_with_what_its_seller_declared():
    """One real request. Run with `uv run pytest -m network`.

    Deselected by default. This is the test that catches eBay changing the
    shape of `localizedAspects`, which the recorded ones structurally cannot.
    """
    from book_watch.config import load_ebay_credentials
    from book_watch.ebay.search import search_listings

    listings = search_listings("9781590171998", limit=1)
    assert listings, "expected at least one listing for a common paperback"

    with ItemDetailClient(EbayTokenProvider(load_ebay_credentials())) as client:
        declared = client.declared_by(listings[0].item_id)

    assert declared.item_id == listings[0].item_id

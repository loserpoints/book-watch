"""Tests for the results page.

No network: the router takes its search function as an argument, so these
drive the real templates against listings the test made up.
"""

import html
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import config as config_module
from book_watch import db
from book_watch import enrichment as enrichment_module
from book_watch import sweeps as sweeps_module
from book_watch.config import DeletionEndpointConfig, MissingCredentialError
from book_watch.ebay.errors import EbaySearchError
from book_watch.ebay.search import Listing, Money
from book_watch.web import listings as listings_module
from book_watch.web import searching as searching_module
from book_watch.web import wantlist as web_wantlist
from book_watch.web.app import create_app

DELETION_CONFIG = DeletionEndpointConfig(
    verification_token="a" * 32,
    endpoint_url="https://book-watch-alan.fly.dev/ebay/deletion",
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
    return lambda query, limit, **_: list(results)


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
    """The three-valued shipping rule, carried through to the page."""
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

    def search(query, limit, **_):
        calls.append(query)
        return []

    response = client_for(search).get("/search")

    assert response.status_code == 200
    assert "/search?isbn=" in response.text
    assert calls == []


def test_a_blank_isbn_is_treated_as_no_isbn():
    calls = []

    def search(query, limit, **_):
        calls.append(query)
        return []

    client_for(search).get("/search?isbn=%20%20")

    assert calls == []


def test_the_limit_reaches_the_search():
    seen = {}

    def search(query, limit, **_):
        seen["query"] = query
        seen["limit"] = limit
        return []

    client_for(search).get("/search?isbn=9780099448396&limit=5")

    assert seen == {"query": "9780099448396", "limit": 5}


@pytest.mark.parametrize("limit", [0, 201])
def test_an_out_of_range_limit_is_rejected_before_ebay_is_asked(limit):
    calls = []

    def search(query, limit, **_):
        calls.append(limit)
        return []

    response = client_for(search).get(f"/search?isbn=x&limit={limit}")

    assert response.status_code == 422
    assert calls == []


def test_an_ebay_failure_is_reported_on_the_page_as_a_bad_gateway():
    def search(query, limit, **_):
        raise EbaySearchError("HTTP 503 from the eBay Browse API")

    response = client_for(search).get("/search?isbn=x")

    assert response.status_code == 502
    assert "eBay could not be searched" in response.text
    assert "503" in response.text


def test_missing_credentials_are_reported_as_a_configuration_problem():
    def search(query, limit, **_):
        raise MissingCredentialError("EBAY_CLIENT_ID is not set.")

    response = client_for(search).get("/search?isbn=x")

    assert response.status_code == 500
    assert "eBay is not configured" in response.text


def test_the_app_does_not_read_ebay_credentials_at_startup(monkeypatch):
    """Load them eagerly and the deployed compliance endpoint stops booting.

    Production holds the deletion secrets and not the eBay keys, and that
    endpoint has an uptime obligation of its own. This is the
    test that stops someone making the search client eager for tidiness.
    """

    def explode(*args, **kwargs):
        raise AssertionError("eBay credentials must not be read at startup")

    # Both modules that can reach a credential. The search client reads them
    # in `searching` and the enrichment wiring in `enrichment`, and patching
    # only one leaves the other free to go eager without failing this test —
    # which is what happened when the search client moved out.
    monkeypatch.setattr(searching_module, "load_ebay_credentials", explode)
    monkeypatch.setattr(enrichment_module, "load_ebay_credentials", explode)

    client = TestClient(create_app(DELETION_CONFIG))

    assert client.get("/health").status_code == 200


def test_searching_without_ebay_keys_fails_loudly_and_breaks_nothing_else(
    monkeypatch,
):
    def missing(*args, **kwargs):
        raise MissingCredentialError("EBAY_CLIENT_ID is not set.")

    monkeypatch.setattr(searching_module, "load_ebay_credentials", missing)
    client = TestClient(create_app(DELETION_CONFIG))

    assert client.get("/search?isbn=x").status_code == 500
    # The endpoint eBay actually depends on is untouched by that failure.
    assert client.get("/health").status_code == 200


def test_the_page_says_where_a_missing_ebay_key_goes(monkeypatch):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "a-cert-id")
    monkeypatch.setattr(
        searching_module,
        "load_ebay_credentials",
        lambda: config_module.load_ebay_credentials(use_dotenv=False),
    )
    client = TestClient(create_app(DELETION_CONFIG))

    page = client.get("/search?isbn=x").text

    assert "EBAY_CLIENT_ID is not set." in page
    assert "Add it under the app&#39;s Secrets on Fly." in page
    assert ".env" not in page


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

    def make(search, enrich=None):
        """`enrich` defaults to doing nothing, never to doing it for real.

        A test that forgot to pass one would otherwise call eBay and Open
        Library from a background task — which `tests/conftest.py` would
        catch, but only after the request had already returned 200.
        """
        app = FastAPI()
        examine = enrich or (lambda work_id: None)
        app.include_router(listings_module.build_router(search, connect, examine))
        # The want-list searches and examines too, now that it owns checking —
        # so it gets the same stubs. Without them it reaches for the real
        # clients and conftest's guard fires, which is how this was caught.
        app.include_router(
            web_wantlist.build_router(connect, search=search, enrich=examine)
        )
        client = TestClient(app)
        # So a test can set up a state the routes cannot reach on their own —
        # a database with history, which is what production has.
        client.app.state.connect = connect
        return client

    return make


def add_book(client, isbn, title=""):
    client.post("/books", data={"isbn": isbn, "title": title, "override": "1"})


def test_a_book_on_the_list_shows_what_is_for_sale(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1")

    assert page.status_code == 200
    assert "Crash" in page.text
    # Delivered, as every price is; the word went in S27.
    assert "$12.98" in visible(page.text)
    assert "https://www.ebay.com/itm/123" in page.text


def test_the_book_page_searches_for_that_book(book_client):
    seen = {}

    def search(query, limit, **_):
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

    Since S18 that word is relative. The page's whole claim is about how
    current its results are, and a timestamp makes the reader do arithmetic to
    find out.
    """
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    assert (
        "fetched 20" in book_client(returning(a_listing())).get("/search?isbn=x").text
    )
    page = client.get("/book/1").text
    # A chip since S34: tapping it is the re-run.
    assert "Checked just now" in visible(page)
    assert re.search(r'href="/book/1\?refresh=1"', page)


# --- the page reads the store ----------------------------------------------


def counting_search(results=None):
    """A search that records every time it was asked."""
    asked = []

    def search(query, limit, **_):
        asked.append(query)
        return [a_listing()] if results is None else list(results)

    return search, asked


def test_views_inside_the_window_do_not_search_again(book_client):
    """Not about the API budget — ten books at the ceiling is 240 searches a
    day against 5,000. It is about results holding still long enough to act
    on: if the list reorders while you check another book, you can lose the
    copy you had decided to buy."""
    search, asked = counting_search()
    client = book_client(search)
    add_book(client, "9780099448396", "Crash")

    client.get("/book/1")
    client.get("/book/1")
    client.get("/book/1")

    assert len(asked) == 1


def test_a_view_after_the_window_searches_again(book_client):
    """The whole point of the slice. Opening a book is a request to see what
    is listed *now*; before this it showed a snapshot from the first-ever view
    and never refreshed it."""
    search, asked = counting_search()
    client = book_client(search)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")

    with client.app.state.connect() as connection:
        connection.execute(
            "UPDATE sweep SET at = datetime('now', '-2 hours')",
        )
        connection.commit()
    client.get("/book/1")

    assert len(asked) == 2


def test_the_window_is_one_place_and_the_route_obeys_it(book_client, monkeypatch):
    """The value is read from `sweeps.CURRENT_FOR` rather than inlined, so
    #72 can read it from somewhere else later without hunting for it."""
    search, asked = counting_search()
    client = book_client(search)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")

    monkeypatch.setattr(sweeps_module, "CURRENT_FOR", timedelta(0))
    client.get("/book/1")

    assert len(asked) == 2


def test_looking_again_searches_again(book_client):
    searches = []

    def search(query, limit, **_):
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
    client = book_client(lambda query, limit, **_: list(listings))
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

    # The visible sentence is the whole fact; tapping it gives the reason in
    # place. It used to be a hover `title`, which a touchscreen never shows.
    assert "Still digging through the shelves." in page
    assert "We ask the public catalogs slowly on purpose" in page
    assert 'title="We ask' not in page


def test_a_copy_only_the_title_matches_goes_below_the_fold(book_client):
    """Text alone never reaches certain: 36% precision on the
    edition question, 12% on one book."""
    client = book_client(returning(a_listing(title="Crash by J. G. Ballard")))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    assert "might be this book" in page


def test_an_empty_result_says_when_it_checked(book_client):
    client = book_client(returning())
    add_book(client, "9780099448396", "Crash")

    page = visible(client.get("/book/1").text)

    assert "Nothing listed in the US right now" in page
    assert "Checked just now" in page
    # The empty US list is the whole reason the toggle exists, so it has to
    # say what to do next rather than leave a blank page.
    assert "Look everywhere" in page


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


def test_a_book_picked_from_a_title_search_carries_no_such_warning(book_client):
    """Nothing was typed: it is searched on the title and author Open Library
    confirmed, which is the normal search for it, not a worse one (#102)."""
    client = book_client(returning(a_listing()))
    client.post(
        "/books/chosen",
        data={"title": "Stoner", "author": "John Williams", "work_id": "OL3511459W"},
    )

    page = client.get("/book/1").text

    assert "Stoner" in page
    assert "not an ISBN" not in page


def test_a_valid_isbn_open_library_does_not_know_carries_no_such_warning(
    book_client,
):
    """Added anyway, and searched by its number — an ISBN search like any other."""
    client = book_client(returning(a_listing()))
    add_book(client, "9781590171998")

    assert "not an ISBN" not in client.get("/book/1").text


def test_the_want_list_links_to_each_book(book_client):
    client = book_client(returning())
    add_book(client, "9780099448396", "Crash")

    assert 'href="/book/1"' in client.get("/").text


def test_an_ebay_failure_on_a_book_page_is_still_a_bad_gateway(book_client):
    def search(query, limit, **_):
        raise EbaySearchError("HTTP 503 from the eBay Browse API")

    client = book_client(search)
    add_book(client, "9780099448396", "Crash")

    assert client.get("/book/1").status_code == 502


# --- when a pass gets scheduled --------------------------------------------
#
# The original condition was "is there a copy eBay has never been asked
# about". After the first pass there never is, so enrichment ran once per book
# and never again — and every later fix to what a pass does was dead code in
# production while passing every test. These start from a database with
# history, which is what production has and what the other tests do not.


def enriching_client(book_client):
    """A client that records which books a pass was scheduled for."""
    scheduled = []
    client = book_client(returning(a_listing()), scheduled.append)
    return client, scheduled


def test_a_book_with_no_finished_pass_is_scheduled_even_with_nothing_unasked(
    book_client,
):
    """The State of grace case: every copy already examined, no pass ever
    finished, and the only thing that could finish one never ran."""
    client, scheduled = enriching_client(book_client)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    scheduled.clear()

    with client.app.state.connect() as connection:
        # Every copy asked about, exactly as production had it.
        connection.execute(
            "INSERT INTO listing_declaration (item_id) SELECT item_id FROM copy"
        )
        connection.commit()

    client.get("/book/1")

    assert scheduled == [1]


def test_a_finished_pass_stops_scheduling(book_client):
    client, scheduled = enriching_client(book_client)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    with client.app.state.connect() as connection:
        connection.execute("UPDATE work SET enriched_at = datetime('now')")
        connection.commit()
    scheduled.clear()

    client.get("/book/1")
    client.get("/book/1")

    assert scheduled == []


def _finish_the_pass(client):
    with client.app.state.connect() as connection:
        connection.execute("UPDATE work SET enriched_at = datetime('now')")
        connection.commit()


def test_looking_again_and_finding_nothing_new_schedules_no_pass(book_client):
    """A refresh that returns the same copies has taught us nothing.

    This used to schedule a pass unconditionally, so every refresh spent Open
    Library requests re-asking about numbers already answered. Their traffic
    is the budget with the least room in it.
    """
    client, scheduled = enriching_client(book_client)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    _finish_the_pass(client)
    scheduled.clear()

    client.get("/book/1?refresh=1")

    assert scheduled == []


def test_looking_again_and_finding_a_new_copy_does_schedule_one(book_client):
    """A copy nobody has examined is the thing a pass exists for."""
    scheduled = []
    results = [a_listing()]
    client = book_client(lambda query, limit, **_: list(results), scheduled.append)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    _finish_the_pass(client)
    scheduled.clear()

    results.append(a_listing(item_id="v1|999|0", title="Crash, another copy"))
    client.get("/book/1?refresh=1")

    assert scheduled == [1]


# --- what I will pay ---------------------------------------------------------


def test_setting_a_ceiling_marks_what_is_under_it(book_client):
    client = book_client(
        returning(
            a_listing(item_id="v1|1|0", price=Money(Decimal("4.00"), "USD")),
            a_listing(item_id="v1|2|0", price=Money(Decimal("30.00"), "USD")),
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")

    client.post("/book/1/ceiling", data={"ceiling": "8.00", "currency": "USD"})
    page = client.get("/book/1").text

    seen = visible(page)
    # ✓ and the words for a reader who cannot see the green. $4 + $3.99, and
    # $30 + $3.99.
    assert seen.count("(under your limit)") == 1
    # Both copies still shown: the ceiling marks, it never filters.
    assert "v1|1|0" in page or "itm/123" in page
    # Over is red with no amount (S61), and said to a screen reader.
    assert seen.count("(over your limit)") == 1
    assert not re.search(r"\$[\d.]+\+? over", seen)


def test_a_copy_without_a_delivered_price_is_not_judged(book_client):
    """S54: even a price alone over the limit says only that shipping is
    unknown. eBay allows that only for local pickup and freight."""
    client = book_client(
        returning(a_listing(price=Money(Decimal("30.00"), "USD"), shipping_cost=None))
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    client.post("/book/1/ceiling", data={"ceiling": "8.00", "currency": "USD"})

    page = visible(client.get("/book/1").text)

    assert "$30 + shipping?" in page
    assert not re.search(r"\$[\d.]+\+? over", page)
    assert "(under your limit)" not in page


def test_the_book_page_is_built_from_the_system(book_client):
    """S34. The limit is a sheet opened from a chip, the photos have somewhere
    to open, and nothing offers to dismiss a copy before dismissing exists
    (#105): a button that does nothing breaks principle 2."""
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    assert 'data-open="limit-sheet"' in page
    assert '<dialog class="sheet" id="limit-sheet"' in page
    assert '<dialog class="photo-view" id="photo-view"' in page
    assert "Dismiss this copy" not in page


def test_a_ceiling_can_be_cleared(book_client):
    """A limit somebody can set and not unset is a trap, and the page is the
    only place to change your mind."""
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")
    client.post("/book/1/ceiling", data={"ceiling": "8.00", "currency": "USD"})

    client.post("/book/1/ceiling", data={"ceiling": "", "currency": "USD"})

    with client.app.state.connect() as connection:
        row = connection.execute(
            "SELECT ceiling, ceiling_currency FROM entry"
        ).fetchone()
    assert (row["ceiling"], row["ceiling_currency"]) == (None, None)


def test_a_ceiling_that_is_not_a_price_is_refused(book_client):
    """Storing it would look like "no copy is under" later, with no clue why."""
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    assert (
        client.post(
            "/book/1/ceiling", data={"ceiling": "cheap", "currency": "USD"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/book/1/ceiling", data={"ceiling": "-5", "currency": "USD"}
        ).status_code
        == 400
    )


def test_a_copy_with_no_stated_shipping_says_so_rather_than_guessing(book_client):
    client = book_client(
        returning(a_listing(price=Money(Decimal("4.00"), "USD"), shipping_cost=None))
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    client.post("/book/1/ceiling", data={"ceiling": "8.00", "currency": "USD"})

    page = visible(client.get("/book/1").text)

    assert "$4 + shipping?" in page
    assert "(under your limit)" not in page


def test_a_copy_with_unknown_shipping_is_listed_after_a_dearer_known_one(book_client):
    """S44: the first copy on the page is always one I know the cost of."""
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                title="Crash, shipping unknown",
                price=Money(Decimal("4.00"), "USD"),
                shipping_cost=None,
            ),
            a_listing(
                item_id="v1|2|0",
                title="Crash, shipping known",
                price=Money(Decimal("9.00"), "USD"),
                shipping_cost=Money(Decimal("1.00"), "USD"),
            ),
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    assert page.index("Crash, shipping known") < page.index("Crash, shipping unknown")
    assert "$4 + shipping?" in page


# --- where this copy sits among the others -----------------------------------


def make_certain(client, isbn="9780099448396", title="Crash"):
    """Give every stored copy a declaration the catalog recognizes.

    Copies reach `certain` on identifiers, never on text, and
    only a certain copy carries a standing — a rank against a set of copies it
    might not belong to would be a rank for a different book.
    """
    with client.app.state.connect() as connection:
        for row in connection.execute("SELECT item_id FROM copy"):
            connection.execute(
                "INSERT OR IGNORE INTO listing_declaration (item_id, isbn, author) "
                "VALUES (?, ?, 'J. G. Ballard')",
                (row["item_id"], isbn),
            )
        connection.execute(
            "INSERT OR IGNORE INTO openlibrary_edition (isbn, found, title) "
            "VALUES (?, 1, ?)",
            (isbn, title),
        )
        connection.commit()


def as_read(page):
    """The page's text with whitespace collapsed, which is what a browser
    renders. A sentence broken across lines in the template is one line on
    screen, and asserting on the template's line breaks would make these
    tests fail on a reflow that changed nothing anybody can see."""
    return " ".join(page.split())


def visible(page):
    """What a reader sees, and what a screen reader hears: tags gone, entities
    decoded, whitespace collapsed. Since S34 a fact is often split across
    elements (a chip's label and its value), and asserting on markup would
    test the markup rather than the fact."""
    kept = re.sub(r'aria-label="([^"]*)"', r"> \1 <", page)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", kept)).split())


def test_a_copy_says_where_it_sits_among_the_others(book_client):
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                price=Money(Decimal("4.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            ),
            a_listing(
                item_id="v1|2|0",
                price=Money(Decimal("30.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            ),
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    # The market once, and the strip of what it asks (S34).
    assert "2 used listed now" in page
    assert "2 asking prices seen, $4 to $30" in page
    # Each copy's place, drawn: every dot a copy of its kind listed now.
    assert "1 of 2 by price among copies listed now" in page
    assert "2 of 2 by price among copies listed now" in page


def test_the_range_is_stated_once_however_many_copies_there_are(book_client):
    """The whole point of the slice. S21 put the range on every copy, which on
    a twelve-copy book was the same clause eight times — one fact crowding out
    the one thing that varies. It is a property of the class, not the copy."""
    client = book_client(
        returning(
            *[
                a_listing(
                    item_id=f"v1|{n}|0",
                    price=Money(Decimal(f"{n + 4}.00"), "USD"),
                    shipping_cost=Money(Decimal("0.00"), "USD"),
                    condition_id="5000",
                )
                for n in range(6)
            ]
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    # The range itself, drawn once as the market's strip.
    assert page.count("6 asking prices seen, $4 to $9") == 1
    # And every copy still says where it sits.
    assert page.count("of 6 by price among copies listed now") == 6


def test_a_new_copy_and_a_used_one_are_never_counted_together(book_client):
    """Two markets rather than two grades. The page must not say 'cheapest of
    3' where one of the three is shrink-wrapped stock from a bulk seller."""
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                price=Money(Decimal("18.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            ),
            a_listing(
                item_id="v1|2|0",
                price=Money(Decimal("21.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="1000",
            ),
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    assert "only used listing" in page
    assert "only new listing" in page
    # Two markets, stated separately, neither pooled into a count of two.
    assert "1 used listed now" in page
    assert "1 new listed now" in page
    assert "2 used listed now" not in page


def test_a_copy_with_no_stated_condition_says_so_rather_than_ranking(book_client):
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                price=Money(Decimal("4.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition=None,
                condition_id=None,
            )
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    assert "can't place: condition unstated" in page
    assert "by price among" not in page


def test_a_copy_with_words_but_no_code_does_not_contradict_itself(book_client):
    """Every row recorded before migration 017 is this: eBay's words stored,
    eBay's number parsed and dropped. A copy whose own line reads "Good" must
    not be told it stated no condition — a page that contradicts itself in
    public is not believed about the things it gets right."""
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                price=Money(Decimal("4.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition="Good",
                condition_id=None,
            )
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = visible(client.get("/book/1").text)

    assert "Good" in page
    assert "can't place: no condition code" in page
    assert "condition unstated" not in page


def test_nothing_on_the_page_says_a_copy_sold(book_client):
    """We observe that a copy was listed at a price and later was
    not; why it went is not something eBay will tell us. The wording is where
    that distinction gets lost, so it is asserted rather than trusted."""
    client = book_client(
        returning(
            a_listing(
                item_id="v1|1|0",
                price=Money(Decimal("4.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            ),
            a_listing(
                item_id="v1|2|0",
                price=Money(Decimal("30.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            ),
        )
    )
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    page = as_read(client.get("/book/1").text).lower()

    for conclusion in ("sold for", "sold at", "went for", "fetched", "sale price"):
        assert conclusion not in page


def test_the_range_on_the_page_spans_copies_that_have_stopped_appearing(book_client):
    """The page must hand the range the wider population, not the copies it is
    drawing. Wiring a correct function to the narrower input passes every
    unit test and is a real failure: a rank and a range
    answer different questions and cannot read the same list.

    A copy that has gone still happened. Losing it would leave the range
    describing only what has *not* sold, which is the slowest-moving end of
    the market — and it would silently narrow every time a book sold well."""
    stock = [
        a_listing(
            item_id="v1|1|0",
            price=Money(Decimal("4.00"), "USD"),
            shipping_cost=Money(Decimal("0.00"), "USD"),
            condition_id="5000",
        ),
        a_listing(
            item_id="v1|2|0",
            price=Money(Decimal("30.00"), "USD"),
            shipping_cost=Money(Decimal("0.00"), "USD"),
            condition_id="5000",
        ),
    ]
    client = book_client(lambda query, limit, **_: list(stock))
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    make_certain(client)

    stock.pop()  # the $30 copy stops appearing
    page = as_read(client.get("/book/1?refresh=1").text)

    page = visible(page)
    assert "only used listing" in page
    # One listed now, two seen, and the strip spans both.
    assert "1 used listed now, 2 seen" in page
    assert "2 asking prices seen, $4 to $30" in page


# --- checking the whole list -------------------------------------------------
#
# The walk is chained rather than timed, so what these guard is mostly
# structural: one request outstanding at a time, every book visited once, and
# a row that says which of the four things is true of it.


def follow(client, url, *, limit=12, responses=False):
    """Walk the chain the way a browser would, returning every response.

    HTMX is not running here, so the trigger has to be followed by hand — and
    following it by hand is also how a test can prove there was only ever one
    to follow. Each response's text, or the responses themselves when asked.
    """
    seen = []
    kept = []
    while url and len(seen) < limit:
        page = client.get(url.replace("&amp;", "&"))
        seen.append(page.text)
        kept.append(page)
        # One outstanding request at a time is the whole design: a second
        # trigger in one response would be two eBay calls and two writers
        # against a database that takes one.
        assert page.text.count('hx-trigger="load"') <= 1, (
            "a step queued more than one next request"
        )
        found = re.search(r'hx-get="([^"]+)"[^>]*hx-trigger="load"', page.text)
        url = found.group(1) if found else None
    return kept if responses else seen


def a_shelf(book_client, *, fails=(), enrich=None):
    """Three books, each with its own copies, and a search that counts calls."""
    asked = []

    def search(query, limit, **_):
        asked.append(query)
        if query in fails:
            raise EbaySearchError("eBay said no")
        return [
            a_listing(
                item_id=f"{query}|{n}",
                title=f"{TITLES[query]} a fine copy",
                price=Money(Decimal(f"{10 + n}.00"), "USD"),
                shipping_cost=Money(Decimal("0.00"), "USD"),
                condition_id="5000",
            )
            for n in range(3)
        ]

    client = book_client(search, enrich)
    for isbn, title in TITLES.items():
        add_book(client, isbn, title)
    return client, asked


TITLES = {
    "9781590171998": "Stoner",
    "9780099448396": "Crash",
    "9781771965231": "Breaking and Entering",
}


def all_certain(client):
    with client.app.state.connect() as connection:
        for row in connection.execute("SELECT item_id FROM copy"):
            isbn = row["item_id"].split("|")[0]
            connection.execute(
                "INSERT OR IGNORE INTO listing_declaration (item_id, isbn) "
                "VALUES (?, ?)",
                (row["item_id"], isbn),
            )
            connection.execute(
                "INSERT OR IGNORE INTO openlibrary_edition (isbn, found, title) "
                "VALUES (?, 1, ?)",
                (isbn, TITLES[isbn]),
            )
        connection.commit()


def test_opening_the_want_list_spends_nothing(book_client):
    """The reason the want list reads the store:
    a list that spent ten seconds before rendering would be a worse list."""
    client, asked = a_shelf(book_client)

    page = client.get("/")

    assert page.status_code == 200
    assert asked == []


def test_a_book_never_checked_says_so_rather_than_nothing_listed(book_client):
    """The worst thing this screen could say. "Nothing listed" about a market
    nobody has asked about is a confident claim with nothing behind it."""
    client, _ = a_shelf(book_client)

    page = as_read(client.get("/").text)

    assert page.count("Not checked yet") == 3
    assert "Nothing listed" not in page


def test_checking_walks_every_book_once(book_client):
    client, asked = a_shelf(book_client)

    steps = follow(client, "/books/check")

    assert sorted(asked) == sorted(TITLES)
    assert "Checked 3 books." in as_read(steps[-1])


def test_the_walk_carries_its_count_rather_than_losing_it(book_client):
    """Each step is a separate request and knows only what it was told."""
    client, _ = a_shelf(book_client)

    steps = [as_read(step) for step in follow(client, "/books/check")]

    assert "Checking 3 books…" in steps[0]
    assert "Checking 2 books…" in steps[1]
    assert "Checking 1 book…" in steps[2]


def test_a_row_says_it_is_being_checked_while_it_is(book_client):
    """Before the search, not after. A row that only ever showed its result
    would leave the list looking frozen for two seconds a book."""
    client, _ = a_shelf(book_client)

    first = as_read(follow(client, "/books/check", limit=1)[0])

    assert first.count("Checking…") == 1


def test_the_gate_stops_a_second_walk_from_spending_anything(book_client):
    client, asked = a_shelf(book_client)
    follow(client, "/books/check")
    asked.clear()

    again = as_read(client.get("/books/check").text)

    assert asked == []
    assert "Everything is current" in again


def test_re_checking_ignores_the_gate(book_client):
    """Matching the book page's re-run: a control that did nothing for
    fifty-nine minutes would be worse than no control."""
    client, asked = a_shelf(book_client)
    follow(client, "/books/check")
    asked.clear()

    follow(client, "/books/check?force=1")

    assert sorted(asked) == sorted(TITLES)


def test_a_failed_search_leaves_that_row_saying_so_and_carries_on(book_client):
    """One dead book must not hide the other nine."""
    client, asked = a_shelf(book_client, fails={"9780099448396"})

    steps = follow(client, "/books/check")

    assert sorted(asked) == sorted(TITLES)
    assert any("Couldn't check just now" in as_read(s) for s in steps)
    assert "Checked 3 books." in as_read(steps[-1])


def test_adding_a_book_starts_checking_it(book_client):
    """Not an exception to "nothing sweeps on page load" — adding a book is an
    explicit act, and it means a book you just added never shows as
    unchecked, which is the state that reads worst on a list."""
    client, _ = a_shelf(book_client)

    page = client.post(
        "/books",
        data={"isbn": "9780156031219", "title": "The Little Prince", "override": "1"},
    ).text

    runner = re.search(r'<div id="sweep-runner"[^>]*>', page)
    assert runner and 'hx-get="/books/4/check' in runner.group(0)
    assert 'hx-trigger="load"' in runner.group(0)


def test_checking_from_the_list_examines_the_new_copies(book_client):
    """As opening the book does. Before, only opening it started the pass, so
    a book checked from the list said "digging" until somebody opened it
    (#129)."""
    examined = []
    client, _ = a_shelf(book_client, enrich=examined.append)

    follow(client, "/books/check")

    assert len(examined) == 3


def test_a_checked_row_says_digging_while_its_pass_runs(book_client):
    during = []

    def examine(work_id):
        during.append(enrichment_module.busy(work_id))

    client, _ = a_shelf(book_client, enrich=examine)

    steps = [visible(step) for step in follow(client, "/books/check")]

    assert during == [True, True, True]
    assert all("digging" in step for step in steps[1:])
    assert not any(enrichment_module.busy(n) for n in (1, 2, 3))


def test_a_failed_check_starts_no_pass(book_client):
    examined = []
    client, _ = a_shelf(book_client, fails=set(TITLES), enrich=examined.append)

    follow(client, "/books/check")

    assert examined == []


def test_a_book_already_being_examined_is_not_examined_twice(book_client):
    examined = []
    client, _ = a_shelf(book_client, enrich=examined.append)
    run = enrichment_module.queued(lambda work_id: None, 1)

    follow(client, "/books/check")
    run()

    assert len(examined) == 2


def test_a_checked_book_leads_with_its_cheapest_used_copy(book_client):
    client, _ = a_shelf(book_client)
    follow(client, "/books/check")
    all_certain(client)

    page = visible(client.get("/").text)

    # The cheapest, delivered (S34: "from", no market word, S26 B5), and the
    # range as the row's strip (#76).
    assert page.count("from $10") == 3
    assert page.count("3 listed") == 3
    assert page.count("3 asking prices seen, $10 to $12") == 3


def test_update_counts_what_it_would_check_and_check_all_asks_first(book_client):
    """S27's pair. Update's count is what pressing it costs; Check all
    overrides the hour, so it asks first and offers Update instead."""
    client, _ = a_shelf(book_client)

    before = visible(client.get("/").text)
    # Nothing checked yet: all three are out of date, so Check all is the same
    # request as Update and has nothing to warn about.
    assert "Update 3" in before
    assert "check-all-sheet" not in client.get("/").text

    follow(client, "/books/check")
    after = client.get("/").text

    assert "All current" in visible(after)
    assert 'data-open="check-all-sheet"' in after
    assert "3 of them were checked within the last hour" in visible(after)
    assert "Don't ask me again" in visible(after)


def header_after(client, step):
    """The header as the page asks for it once a response has settled: only
    when the response says the list changed, sending the runner's inputs as
    `hx-include` would, so it knows whether a check is still running. None
    when the response doesn't ask."""
    if step.headers.get("HX-Trigger-After-Settle") != "list-changed":
        return None
    walking = 'name="walking"' in step.text
    return client.get("/books/bar" + ("?walking=1" if walking else "")).text


def walk_watching_the_header(client, url="/books/check"):
    """Follow a check step by step, asking for the header after each step as
    the page does, before the next step runs."""
    headers = []
    while url:
        step = client.get(url.replace("&amp;", "&"))
        headers.append(header_after(client, step))
        found = re.search(r'hx-get="([^"]+)"[^>]*hx-trigger="load"', step.text)
        url = found.group(1) if found else None
    return headers


def button(page, label):
    """The opening tag of the button a reader sees as `label`."""
    found = re.search(rf"<button([^>]*)>\s*{label}", page)
    assert found, f"no {label!r} button"
    return found.group(1)


def test_the_header_counts_down_as_a_check_runs(book_client):
    """S67 (#244): it kept the count it had when the page loaded, so Update
    still said "Update 3" after checking all three."""
    client, _ = a_shelf(book_client)

    headers = walk_watching_the_header(client)

    assert None not in headers
    said = [visible(h) for h in headers]
    assert "Update 3" in said[0]
    assert "Update 2" in said[1]
    assert "Update 1" in said[2]
    assert "All current" in said[3]


def test_after_a_check_check_all_asks_first(book_client):
    """S67 (#244): drawn when nothing was fresh, Check all stayed the button
    that runs at once, and a second tap checked everything again unasked."""
    client, _ = a_shelf(book_client)
    assert "check-all-sheet" not in client.get("/").text

    last = follow(client, "/books/check", responses=True)[-1]
    header = header_after(client, last)

    assert 'data-open="check-all-sheet"' in button(header, "Check all")
    assert "3 of them were checked within the last hour" in visible(header)


def test_while_a_check_runs_neither_button_starts_another(book_client):
    """A second walk would fight the first over the runner."""
    client, _ = a_shelf(book_client)

    headers = walk_watching_the_header(client)
    during, after = headers[0], headers[-1]

    assert "disabled" in button(during, "Update")
    assert "disabled" in button(during, "Check all")
    assert "disabled" not in button(after, "Check all")


def test_a_book_just_added_holds_the_buttons_while_it_checks(book_client):
    """Adding a book starts its check, so the list it comes back with has one
    running."""
    client, _ = a_shelf(book_client)
    follow(client, "/books/check")

    page = client.post(
        "/books",
        data={"isbn": "9780156031219", "title": "The Little Prince", "override": "1"},
        headers={"HX-Request": "true"},
    ).text

    assert "disabled" in button(page, "Update")
    assert "disabled" in button(page, "Check all")


def test_a_row_that_finishes_digging_tells_the_header(book_client, monkeypatch):
    """Copies count toward "Under limit" only once examined, which can end
    after the check's last step."""
    client, _ = a_shelf(book_client)
    follow(client, "/books/check")

    monkeypatch.setattr(enrichment_module, "busy", lambda work_id: True)
    digging = client.get("/books/1/row")
    monkeypatch.setattr(enrichment_module, "busy", lambda work_id: False)
    done = client.get("/books/1/row")

    assert "digging" in visible(digging.text)
    assert digging.headers.get("HX-Trigger-After-Settle") is None
    assert done.headers.get("HX-Trigger-After-Settle") == "list-changed"


def test_a_row_can_be_removed_and_asks_first(book_client):
    """S26 B6: a trash icon, and it keeps its confirmation."""
    client, _ = a_shelf(book_client)

    page = client.get("/").text

    assert 'hx-confirm="Remove Crash from the list?"' in page
    assert 'hx-delete="/books/2"' in page


def test_the_ceiling_shows_against_the_cheapest_copy(book_client):
    client, _ = a_shelf(book_client)
    follow(client, "/books/check")
    all_certain(client)
    client.post("/book/1/ceiling", data={"ceiling": "11.50", "currency": "USD"})

    page = as_read(client.get("/").text)

    # One book has a ceiling; the other two say nothing about limits.
    assert page.count("under your limit") == 1


# --- new since I last looked (S39, #142) -------------------------------------


def test_copies_new_since_i_last_looked_are_marked_on_the_list_and_the_book(
    book_client,
):
    client, _ = a_shelf(book_client)
    follow(client, "/books/check")
    all_certain(client)
    first = client.get("/book/2").text
    assert "tag-accent" not in first  # Nothing is new on a first visit.

    # Three days pass. Since then: one copy newly listed, one relisted with its
    # old listing date, and one I had already seen.
    with client.app.state.connect() as connection:
        connection.execute(
            "UPDATE entry SET looked_at = datetime('now', '-3 days') WHERE id = 2"
        )
        connection.execute(
            "UPDATE copy SET first_seen_at = datetime('now', '-4 days') "
            "WHERE item_id LIKE '9780099448396|%'"
        )
        connection.execute(
            "UPDATE copy SET first_seen_at = datetime('now', '-1 day'), "
            "listed_at = datetime('now', '-1 day') WHERE item_id = '9780099448396|0'"
        )
        connection.execute(
            "UPDATE copy SET first_seen_at = datetime('now', '-1 day'), "
            "listed_at = '2026-01-01T00:00:00+00:00' "
            "WHERE item_id = '9780099448396|1'"
        )
        connection.commit()

    assert "1 new" in visible(client.get("/").text)

    book = client.get("/book/2").text
    assert book.count("tag-accent") == 1
    # A chip tapped on the page reloads it. Same visit, same marks.
    assert client.get("/book/2?everywhere=0").text.count("tag-accent") == 1
    # Seen now, so the list stops counting it.
    assert " new " not in visible(client.get("/").text)


# --- back from a book goes to the want list (S45) -----------------------------

HTMX = {"HX-Request": "true"}


def test_a_limit_saved_through_htmx_reloads_the_page_in_place(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    response = client.post(
        "/book/1/ceiling", data={"ceiling": "8.00", "currency": "USD"}, headers=HTMX
    )

    assert response.status_code == 204
    assert response.headers["HX-Refresh"] == "true"
    assert "$8" in visible(client.get("/book/1").text)


def test_a_limit_that_cannot_be_read_is_answered_inside_the_sheet(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    response = client.post(
        "/book/1/ceiling", data={"ceiling": "cheap", "currency": "USD"}, headers=HTMX
    )

    assert response.status_code == 200
    assert 'class="sheet-error"' in response.text
    assert "HX-Refresh" not in response.headers
    assert "Limit none" in visible(client.get("/book/1").text)


@pytest.mark.parametrize(
    ("asked", "shown"),
    [
        ("/book/1?refresh=1", "/book/1"),
        ("/book/1?everywhere=1&refresh=1", "/book/1?everywhere=1"),
    ],
)
def test_after_searching_again_the_page_drops_refresh(book_client, asked, shown):
    """So a reload, or a return to the page, does not search eBay again."""
    search, asked_for = counting_search([a_listing()])
    client = book_client(search)
    add_book(client, "9780099448396", "Crash")
    client.get("/book/1")
    before = len(asked_for)

    response = client.get(asked, follow_redirects=False)

    assert len(asked_for) == before + 1
    assert response.status_code == 303
    assert response.headers["location"] == shown


def test_the_chips_that_show_the_book_another_way_replace_the_page(book_client):
    client = book_client(returning(a_listing()))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1").text

    for chip in ('"/book/1?everywhere=1"', '"/book/1?refresh=1"'):
        tag = re.search(r"<a[^>]*href=" + re.escape(chip) + r"[^>]*>", page)
        assert tag and "data-replace" in tag.group(0)


# --- when a copy was listed, and newest first (S62) ---------------------------


def dated(item, price, days_ago):
    return a_listing(
        item_id=f"v1|{item}|0",
        item_web_url=f"https://www.ebay.com/itm/{item}",
        price=Money(Decimal(price), "USD"),
        listing_date=None
        if days_ago is None
        else datetime.now(UTC) - timedelta(days=days_ago),
    )


THREE = (dated(111, "5.00", 60), dated(222, "9.00", 2), dated(333, "7.00", None))


def order(page):
    return [int(n) for n in re.findall(r"ebay\.com/itm/(\d{3})", page)]


def test_each_copy_says_when_it_was_listed_and_an_undated_one_says_nothing(
    book_client,
):
    client = book_client(returning(*THREE))
    add_book(client, "9780099448396", "Crash")

    page = visible(client.get("/book/1").text)

    assert "listed 8w" in page
    assert "listed 2d" in page
    assert page.count("listed ") == 2


def test_copies_are_cheapest_first_unless_newest_is_asked_for(book_client):
    client = book_client(returning(*THREE))
    add_book(client, "9780099448396", "Crash")

    assert order(client.get("/book/1").text) == [111, 333, 222]
    # Newest first, and a copy with no date last.
    assert order(client.get("/book/1?sort=newest").text) == [222, 111, 333]


def test_the_order_rides_along_on_every_link_the_page_makes(book_client):
    client = book_client(returning(*THREE))
    add_book(client, "9780099448396", "Crash")

    page = client.get("/book/1?sort=newest").text

    assert re.search(r'<b aria-current="true">Newest</b>', page)
    assert 'href="/book/1?everywhere=1&amp;sort=newest"' in page
    assert 'href="/book/1?sort=newest&amp;refresh=1"' in page
    # Back to cheapest replaces the page rather than adding to the history.
    assert '<a href="/book/1" data-replace>Cheapest</a>' in page


def test_one_copy_offers_no_order_to_choose(book_client):
    client = book_client(returning(THREE[0]))
    add_book(client, "9780099448396", "Crash")

    page = visible(client.get("/book/1").text)

    assert "Newest" not in page

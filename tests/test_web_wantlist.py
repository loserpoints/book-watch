"""Tests for the want-list screens, driven through the real templates."""

import dataclasses
import re
from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import db, enrichment
from book_watch.config import DeletionEndpointConfig
from book_watch.openlibrary import Candidate, EditionIdentity, OpenLibraryUnavailable
from book_watch.openlibrary.budget import DAILY_CEILING
from book_watch.web import wantlist as web_wantlist
from book_watch.web.app import create_app

DELETION_CONFIG = DeletionEndpointConfig(
    verification_token="a" * 32,
    endpoint_url="https://book-watch-alan.fly.dev/ebay/deletion",
)


CRASH = EditionIdentity(
    isbn="9780099448396",
    title="Crash",
    work_id="OL2745977W",
    publisher="Vintage",
    published="1995",
    physical_format="Paperback",
)

CANDIDATES = [
    Candidate(
        work_id="OL3511459W",
        title="Stoner",
        authors=("John Williams",),
        first_published=1965,
        edition_count=49,
    ),
    Candidate(
        work_id="OL26589081W",
        title="John Williams : Collected Novels",
        authors=("John Williams",),
        first_published=2021,
        edition_count=2,
    ),
]


class FakeCatalog:
    """Stands in for Open Library, and records what it was asked.

    Every test gets one of these. `tests/conftest.py` makes a real request a
    loud failure, so forgetting to pass a stub cannot quietly turn the suite
    into traffic against a non-profit.
    """

    def __init__(
        self, *, identities=None, candidates=(), unavailable=False, work_covers=None
    ):
        self.identities = identities if identities is not None else {CRASH.isbn: CRASH}
        self.candidates = list(candidates)
        self.unavailable = unavailable
        self.work_covers = work_covers or {}
        self.asked = []

    def identify_isbn(self, isbn):
        if self.unavailable:
            raise OpenLibraryUnavailable("open library is down")
        self.asked.append(isbn)
        return self.identities.get(isbn)

    def search_works(self, title, author=None, **_):
        if self.unavailable:
            raise OpenLibraryUnavailable("open library is down")
        self.asked.append((title, author))
        return self.candidates

    def work_cover(self, work_id):
        if self.unavailable:
            raise OpenLibraryUnavailable("open library is down")
        self.asked.append(("cover", work_id))
        return self.work_covers.get(work_id)


def build_client(tmp_path, catalog):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    def never_searches(*args, **kwargs):
        raise AssertionError(
            "These tests are about the list itself and must not search eBay. "
            "The router can search now that it owns checking, so saying so "
            "here is cheaper than relying on conftest to catch it."
        )

    app = FastAPI()
    app.include_router(
        web_wantlist.build_router(connect, catalog, search=never_searches)
    )
    # So a test can set up a state the routes cannot reach on their own.
    app.state.connect = connect
    return TestClient(app)


@pytest.fixture
def catalog():
    return FakeCatalog()


@pytest.fixture
def client(tmp_path, catalog):
    return build_client(tmp_path, catalog)


def add(client, isbn, title="", override=""):
    return client.post(
        "/books", data={"isbn": isbn, "title": title, "override": override}
    )


def test_an_empty_list_says_so(client):
    page = client.get("/").text

    assert "Nothing on the list yet" in page


def test_an_empty_list_offers_nothing_to_check(client):
    """S69 (#217): with no books there is nothing to check, so no button."""
    page = client.get("/").text

    assert "check-btn" not in page
    assert "Under limit" not in page


def test_a_book_is_added_and_appears_on_the_list(client):
    response = add(client, "9780099448396", "Crash")

    assert response.status_code == 200
    assert "Crash" in response.text
    # The ISBN left the row in S34 (S26 B3); it stays on the book page.
    assert 'href="/book/1"' in response.text
    assert "Nothing on the list yet" not in response.text


def test_an_isbn10_is_stored_as_the_isbn13_of_the_same_book(client):
    """Otherwise the same book could be added twice under two spellings."""
    add(client, "0099448394")

    # Read from the store: the ISBN is no longer on the list row (S34).
    with client.app.state.connect() as connection:
        typed = connection.execute("SELECT typed FROM entry").fetchone()["typed"]
    assert typed == "9780099448396"


def test_a_mistyped_isbn_is_refused_and_not_added(client):
    response = add(client, "9780099448390")

    assert response.status_code == 400
    assert "not a valid ISBN" in response.text
    assert "Nothing on the list yet" in response.text


def test_a_refused_isbn_offers_to_add_it_anyway(client):
    """Some books never had an ISBN; a check digit cannot tell that from a typo."""
    response = add(client, "The Riddle of the Sands")

    assert response.status_code == 400
    assert 'name="override"' in response.text
    assert "anyway" in response.text


def test_overriding_adds_the_text_exactly_as_typed(client):
    add(client, "The Riddle of the Sands 1903", override="1")
    page = client.get("/").text

    assert "The Riddle of the Sands 1903" in page


def test_the_typed_value_survives_a_refusal(client):
    """So the override button is one click, not a retype."""
    response = add(client, "not-an-isbn", "Childers")

    assert 'value="not-an-isbn"' in response.text
    assert 'value="Childers"' in response.text


def test_adding_the_same_book_twice_is_a_visible_message_not_a_crash(client):
    add(client, "9780099448396")
    response = add(client, "978-0-09-944839-6")  # same book, typed differently

    assert response.status_code == 409
    assert "already on the list" in response.text


def test_an_empty_isbn_is_refused(client):
    response = add(client, "   ")

    assert response.status_code == 400
    assert "Enter a title, or an ISBN" in response.text


def test_a_book_can_be_removed(client):
    add(client, "9780099448396", "Crash")
    book_id = 1

    response = client.delete(f"/books/{book_id}")

    assert response.status_code == 200
    assert "Nothing on the list yet" in response.text
    # Re-fetched, so this is the stored state rather than the fragment the
    # delete happened to return. Asserting the ISBN is *absent* would not work:
    # it is also the add form's placeholder.
    assert "Nothing on the list yet" in client.get("/").text


def test_removing_a_book_returns_only_the_list(client):
    """htmx swaps this fragment in, so it must not carry the whole page."""
    add(client, "9780099448396")

    response = client.delete("/books/1")

    assert 'id="want-list"' in response.text
    assert "<html" not in response.text


def test_removing_something_already_gone_is_not_an_error(client):
    response = client.delete("/books/999")

    assert response.status_code == 200


def test_a_title_cannot_inject_markup(client):
    """Through the override, which is the only path that stores text as typed."""
    add(client, "<script>alert('xss')</script>", override="1")
    page = client.get("/").text

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


# --- adding by number, which now says what the number is --------------------


def test_the_catalog_title_is_shown_rather_than_the_one_typed(client):
    """The reason this slice touches the ISBN path at all.

    A valid ISBN that names the wrong book is invisible to every check this
    project has. Keeping the typed title would hide the one thing that reveals
    it — an ISBN believed to be one book coming back as another.
    """
    response = add(client, "9780099448396", "The Girl with the Dragon Tattoo")

    assert "Crash" in response.text
    assert "Dragon Tattoo" not in response.text


def test_a_number_open_library_does_not_hold_is_offered_not_refused(client):
    """Usually a mistyped digit, occasionally a real book it does not hold."""
    response = add(client, "9781590171998")

    assert response.status_code == 404
    assert "no record of" in response.text
    assert 'name="override"' in response.text
    assert "Nothing on the list yet" in response.text


def test_a_number_added_anyway_says_it_was_not_recognized(client):
    add(client, "9781590171998", override="1")

    assert "Unrecognized ISBN" in client.get("/").text


def test_open_library_being_down_is_a_message_and_an_offer(tmp_path):
    """Not a 500, and not a silent add either — the check simply did not happen."""
    client = build_client(tmp_path, FakeCatalog(unavailable=True))

    response = add(client, "9780099448396")

    assert response.status_code == 503
    assert "could not be reached" in response.text
    assert 'name="override"' in response.text


def test_an_override_asks_open_library_nothing(catalog, client):
    """The person has already decided. Asking again would be noise on a service
    that asks for low volume."""
    add(client, "9781590171998", override="1")

    assert catalog.asked == []


# --- adding by title --------------------------------------------------------


def find(client, title, author=""):
    return client.post("/books", data={"title": title, "author": author})


def test_a_title_search_offers_candidates_to_choose_from(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    response = find(client, "stoner", "john williams")

    assert "Which one?" in response.text
    assert "Stoner" in response.text
    # The omnibus is in the list too, which is the point of choosing.
    assert "Collected Novels" in response.text
    assert "Nothing on the list yet" in response.text


def test_candidates_carry_enough_to_tell_them_apart(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    page = find(client, "stoner").text

    assert "John Williams" in page
    assert "1965" in page
    assert "49 editions" in page


def test_picking_a_candidate_puts_it_on_the_list(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    response = client.post(
        "/books/chosen",
        data={"title": "Stoner", "author": "John Williams", "work_id": "OL3511459W"},
    )

    assert response.status_code == 200
    assert "Stoner" in response.text
    assert "Nothing on the list yet" not in response.text


# --- the add sheet (S34) ----------------------------------------------------


def test_adding_is_a_button_and_a_sheet_not_a_form_on_the_list(client):
    """S26 L1: too much room for something done occasionally."""
    page = client.get("/").text

    assert 'class="fab" data-open="add-sheet"' in page
    assert '<dialog class="sheet" id="add-sheet"' in page
    # Closed until asked for: nothing came back from a search yet.
    assert "data-autoopen" not in page


def test_the_sheet_reopens_with_the_results(tmp_path):
    """The answer appears where the question was asked."""
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    page = find(client, "stoner").text

    assert 'id="add-sheet" aria-labelledby="add-sheet-title" data-autoopen' in page
    assert 'value="title" checked' in page


def test_each_result_is_one_button_that_adds_it(tmp_path):
    """Principle 5: the whole row is the target, and it posts what the
    picker needs rather than making it ask Open Library again."""
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    page = find(client, "stoner").text

    assert page.count('class="candidate-hit"') == len(CANDIDATES)
    assert 'aria-label="Add Stoner by John Williams, 1965"' in page
    assert 'name="work_id" value="OL3511459W"' in page
    # Never inside the search form: a browser drops a form nested in a form,
    # and the row's button then submits the search instead. It did, once.
    search_form = re.search(
        r'<form class="sheet-form"[^>]*action="/books">.*?</form>', page, re.S
    )
    assert search_form and "candidate-hit" not in search_form.group(0)


def test_a_result_already_on_the_list_says_so_instead_of_adding(tmp_path):
    """S27: *On your list*, as nzb360's *In Library* does."""
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))
    client.post(
        "/books/chosen",
        data={"title": "Stoner", "author": "John Williams", "work_id": "OL3511459W"},
    )

    page = find(client, "stoner").text

    assert "On your list" in page
    assert 'name="work_id" value="OL3511459W"' not in page
    assert page.count('class="candidate-hit"') == len(CANDIDATES) - 1


def test_an_isbn_error_reopens_the_sheet_on_the_isbn_side(client):
    page = add(client, "9780099448391").text

    assert "data-autoopen" in page
    assert 'value="isbn" checked' in page
    assert "not a valid ISBN" in page


def test_a_title_search_finding_nothing_says_so_and_suggests_the_isbn(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=[]))

    response = find(client, "a book that does not exist")

    assert response.status_code == 404
    assert "Nothing found" in response.text
    assert "by ISBN" in response.text


def test_a_title_search_sends_the_author_along(catalog, client):
    catalog.candidates = CANDIDATES
    find(client, "stoner", "john williams")

    assert catalog.asked == [("stoner", "john williams")]


def test_open_library_being_down_during_a_search_says_so(tmp_path):
    client = build_client(tmp_path, FakeCatalog(unavailable=True))

    response = find(client, "stoner")

    assert response.status_code == 503
    assert "could not be reached" in response.text
    # The escape hatch still exists while it is down.
    assert "ISBN" in response.text


def test_adding_a_book_costs_one_request(catalog, client):
    """The ten to fifteen a book eventually costs are its listings'."""
    add(client, "9780099448396")

    assert len(catalog.asked) == 1


def test_the_app_does_not_open_the_database_at_startup(monkeypatch):
    """Same rule as the eBay client: the compliance endpoint must start even
    when everything else is misconfigured."""

    def explode(*args, **kwargs):
        raise AssertionError("the database must not be opened at startup")

    monkeypatch.setattr(web_wantlist, "load_database_path", explode)

    app_client = TestClient(create_app(DELETION_CONFIG))

    assert app_client.get("/health").status_code == 200


# --- the tag that says work is outstanding ---------------------------------


def outstanding(client):
    """A book with copies found and not yet examined. Returns its work id."""
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute("UPDATE work SET copies_fetched_at = datetime('now')")
        connection.commit()
        return connection.execute("SELECT id FROM work").fetchone()["id"]


def test_a_book_being_examined_says_so(client):
    """The tag the page renders, not just the property behind it.

    Asserted here because it once did not render at all: the property was
    right, the template edit silently did not apply, and nothing failed.
    """
    work_id = outstanding(client)
    run = enrichment.queued(lambda work_id: None, work_id)

    assert 'class="explain digging"' in client.get("/").text
    run()


def test_a_digging_row_asks_for_itself_until_it_is_done(client):
    work_id = outstanding(client)
    run = enrichment.queued(lambda work_id: None, work_id)

    row = re.search(r'<li class="book-row"[^>]*>', client.get("/").text).group(0)
    assert 'hx-get="/books/1/row"' in row
    assert 'hx-trigger="every ' in row
    run()
    row = client.get("/books/1/row").text

    assert 'class="explain digging"' not in row
    assert "hx-trigger" not in row


def test_a_book_nothing_is_examining_does_not_claim_to_be(client):
    """Copies wait for the next check. Saying "digging" meanwhile would claim
    work nobody is doing (#129)."""
    outstanding(client)

    page = client.get("/").text

    assert 'class="explain digging"' not in page
    assert "Throttled" not in page
    assert "/row" not in page


def test_a_book_waiting_on_the_open_library_ceiling_says_throttled(client):
    outstanding(client)
    with client.app.state.connect() as connection:
        connection.executemany(
            "INSERT INTO openlibrary_call (endpoint) VALUES (?)",
            [("isbn",)] * DAILY_CEILING,
        )
        connection.commit()

    page = client.get("/").text

    assert "Throttled" in page
    assert 'class="explain digging"' not in page
    assert "/row" not in page


def test_a_scheduled_pass_that_fails_to_start_stops_the_digging(client):
    """A pass that dies before it begins, say for want of an eBay key, must
    not leave its book digging and asking for itself for good."""
    work_id = outstanding(client)

    def no_credentials(work_id):
        raise RuntimeError("EBAY_CLIENT_ID is not set.")

    run = enrichment.queued(no_credentials, work_id)
    with pytest.raises(RuntimeError):
        run()

    assert 'class="explain digging"' not in client.get("/").text


def test_a_row_removed_while_digging_answers_with_nothing(client):
    assert client.get("/books/99/row").text == ""


def test_a_book_nobody_has_opened_does_not_claim_to_be_working(client):
    """No copies means nothing to dig through. The app does not advertise
    work it has not started."""
    add(client, "9780099448396", "Crash")

    assert 'class="explain digging"' not in client.get("/").text


def test_a_finished_book_stops_saying_it(client):
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute(
            "UPDATE work SET copies_fetched_at = datetime('now'), "
            "enriched_at = datetime('now')"
        )
        connection.commit()

    assert 'class="explain digging"' not in client.get("/").text


# --- covers -----------------------------------------------------------------
#
# The page points at Open Library's cover server; only the ids
# are ours, and learning one is never allowed to hold up the list.

STONER_COVER = 6980524
COVER_URL = f"https://covers.openlibrary.org/b/id/{STONER_COVER}-M.jpg?default=false"


def pick(client, cover_id=""):
    return client.post(
        "/books/chosen",
        data={
            "title": "Stoner",
            "author": "John Williams",
            "work_id": "OL3511459W",
            "cover_id": cover_id,
        },
    )


def test_candidates_show_their_covers_and_carry_them_to_the_list(tmp_path):
    with_cover = [dataclasses.replace(CANDIDATES[0], cover_id=STONER_COVER)]
    client = build_client(tmp_path, FakeCatalog(candidates=with_cover))

    page = find(client, "stoner").text

    assert COVER_URL in page
    assert f'name="cover_id" value="{STONER_COVER}"' in page


def test_a_picked_book_shows_its_cover_for_no_further_request(tmp_path):
    catalog = FakeCatalog()
    client = build_client(tmp_path, catalog)

    page = pick(client, str(STONER_COVER)).text

    assert COVER_URL in page
    assert catalog.asked == []


def test_a_picked_book_open_library_has_no_cover_for_shows_the_placeholder(tmp_path):
    client = build_client(tmp_path, FakeCatalog())

    page = pick(client).text

    assert 'class="cover-ph-title">Stoner<' in page
    # Nothing to load: Open Library already said so, and asking again on
    # every view would be asking for an answer we have.
    assert "/cover" not in page.split('id="want-list"')[1]
    assert "<img" not in page.split('id="want-list"')[1]


def test_a_book_added_by_number_shows_its_editions_cover(tmp_path):
    crash = dataclasses.replace(CRASH, cover_id=240726)
    catalog = FakeCatalog(identities={CRASH.isbn: crash})
    client = build_client(tmp_path, catalog)

    page = add(client, CRASH.isbn).text

    assert "b/id/240726-M.jpg" in page
    assert len(catalog.asked) == 1


def test_a_book_added_by_number_with_no_edition_cover_asks_later(tmp_path):
    """The work's cover is still unknown, and finding out is not worth a wait."""
    catalog = FakeCatalog()
    client = build_client(tmp_path, catalog)

    page = add(client, CRASH.isbn).text

    assert 'src="/books/1/cover"' in page
    assert catalog.asked == [CRASH.isbn]


def test_rendering_the_list_asks_open_library_nothing(tmp_path):
    catalog = FakeCatalog()
    client = build_client(tmp_path, catalog)
    add(client, CRASH.isbn)
    pick(client)
    before = list(catalog.asked)

    client.get("/")

    assert catalog.asked == before


def test_the_cover_route_learns_the_cover_once_and_sends_the_browser_there(tmp_path):
    catalog = FakeCatalog(work_covers={CRASH.work_id: 240726})
    client = build_client(tmp_path, catalog)
    add(client, CRASH.isbn)

    first = client.get("/books/1/cover", follow_redirects=False)
    second = client.get("/books/1/cover", follow_redirects=False)

    assert first.status_code == second.status_code == 302
    assert first.headers["location"].endswith("/b/id/240726-M.jpg?default=false")
    assert catalog.asked.count(("cover", CRASH.work_id)) == 1
    # And the list now points there itself, so the route is not needed again.
    assert "b/id/240726-M.jpg" in client.get("/").text


def test_no_cover_is_a_404_and_the_list_stops_asking(tmp_path):
    client = build_client(tmp_path, FakeCatalog())
    add(client, CRASH.isbn)

    response = client.get("/books/1/cover", follow_redirects=False)

    assert response.status_code == 404
    assert 'src="/books/1/cover"' not in client.get("/").text


def test_open_library_being_down_leaves_the_cover_to_be_asked_for_next_time(tmp_path):
    catalog = FakeCatalog(work_covers={CRASH.work_id: 240726})
    client = build_client(tmp_path, catalog)
    add(client, CRASH.isbn)

    catalog.unavailable = True
    assert client.get("/books/1/cover", follow_redirects=False).status_code == 404
    catalog.unavailable = False

    assert client.get("/books/1/cover", follow_redirects=False).status_code == 302


def test_a_cover_for_a_book_that_is_not_there_is_a_404(client):
    assert client.get("/books/99/cover").status_code == 404


def test_the_list_credits_open_library_for_its_covers(tmp_path):
    client = build_client(tmp_path, FakeCatalog())

    page = pick(client).text

    assert 'href="https://openlibrary.org"' in page


def test_a_book_added_by_number_before_work_ids_gets_its_cover(tmp_path):
    """The *State of Grace* case: carried across by migration 003 with no work."""
    crash = dataclasses.replace(CRASH, cover_id=240726)
    catalog = FakeCatalog(identities={CRASH.isbn: crash})
    client = build_client(tmp_path, catalog)
    with closing(client.app.state.connect()) as connection:
        work_id = connection.execute(
            "INSERT INTO work (title) VALUES ('Crash')"
        ).lastrowid
        connection.execute(
            "INSERT INTO entry (work_id, hunt, typed) VALUES (?, 'reader', ?)",
            (work_id, CRASH.isbn),
        )

    response = client.get("/books/1/cover", follow_redirects=False)

    assert response.status_code == 302
    assert "b/id/240726-M.jpg" in response.headers["location"]
    assert catalog.asked == [CRASH.isbn]


# --- the morning check ------------------------------------------------------


def test_the_list_says_when_the_morning_check_failed(client):
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute(
            "INSERT INTO daily_run (finished_at, outcome, books, failed) "
            "VALUES (datetime('now'), 'failed', 1, 1)"
        )
        connection.commit()

    page = client.get("/").text

    assert "Daily check failed" in page
    assert "couldn&#39;t search 1 of 1 books" in page


def test_a_failed_morning_check_is_plain_text_under_the_title(client):
    """S69 (#217): the notice reads as a book's page says its AbeBooks check
    failed, under the title and before the button that fixes it, not as a
    pill beside it."""
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute(
            "INSERT INTO daily_run (finished_at, outcome, books, failed) "
            "VALUES (datetime('now'), 'failed', 1, 1)"
        )
        connection.commit()

    page = client.get("/").text

    assert re.search(r'<details class="[^"]*daily-note', page)
    assert "alert-pill" not in page
    assert page.index("<h1>Want list</h1>") < page.index("Daily check failed")
    assert page.index("Daily check failed") < page.index("check-btn")
    assert "Tap Check to search them now." in page


def test_the_list_says_nothing_when_the_morning_check_went_well(client):
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute(
            "INSERT INTO daily_run (finished_at, outcome, books) "
            "VALUES (datetime('now'), 'ok', 1)"
        )
        connection.commit()

    assert "Daily check" not in client.get("/").text


# --- adding leaves nothing in the history (S45) --------------------------------

HTMX = {"HX-Request": "true"}


def test_a_title_search_through_htmx_answers_inside_the_sheet(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    response = client.post("/books", data={"title": "stoner"}, headers=HTMX)

    assert response.status_code == 200
    assert "Which one?" in response.text
    assert "Want list" not in response.text


def test_an_isbn_error_through_htmx_is_shown_in_the_sheet_with_its_offer(client):
    response = client.post("/books", data={"isbn": "9780099448397"}, headers=HTMX)

    # htmx swaps only a success in, and the error is what the sheet shows.
    assert response.status_code == 200
    assert "is not a valid ISBN" in response.text
    assert "anyway" in response.text


def test_a_book_added_through_htmx_swaps_the_list_and_empties_the_sheet(tmp_path):
    client = build_client(tmp_path, FakeCatalog(candidates=CANDIDATES))

    response = client.post(
        "/books/chosen",
        data={"title": "Stoner", "author": "John Williams", "work_id": "OL3511459W"},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#want-list"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Trigger"] == "added"
    assert 'id="want-list"' in response.text
    assert "Stoner" in response.text
    assert 'id="add-sheet-body" hx-swap-oob="innerHTML"' in response.text
    assert "Which one?" not in response.text
    assert "Stoner" in client.get("/").text


def test_without_htmx_adding_still_answers_with_the_whole_page(client):
    response = add(client, "9780099448396", "Crash", override="1")

    assert response.status_code == 200
    assert "<h1>Want list</h1>" in response.text
    assert "HX-Retarget" not in response.headers


# --- under the limit (S60) ---------------------------------------------------


def priced(verdict):
    """What `standing.glance` says of a book whose cheapest copy is `verdict`,
    or of a book never checked when `verdict` is None."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from book_watch.ebay.search import Money
    from book_watch.standing import Glance, Headline, Market

    if verdict is None:
        return Glance(checked=None, listed=0, uncertain=0, headline=None)
    price = Money(Decimal("9.00"), "USD")
    return Glance(
        checked=datetime.now(UTC),
        listed=1,
        uncertain=0,
        headline=Headline(
            market=Market(listed=1, seen=1, low=price, high=price),
            cheapest=price,
            verdict=verdict,
        ),
    )


@pytest.fixture
def three_books(client, monkeypatch):
    """Stoner under its limit, Crash over it, and Kindred with no limit."""
    from book_watch import standing, wantlist

    verdicts = {}
    with closing(client.app.state.connect()) as connection:
        for title, verdict in (
            ("Stoner", "under"),
            ("Crash", "over"),
            ("Kindred", "no limit"),
        ):
            book = wantlist.add_identified(connection, title=title)
            verdicts[book.id] = verdict
        connection.commit()
    monkeypatch.setattr(
        standing, "glance", lambda connection, book, **_: priced(verdicts.get(book.id))
    )
    return verdicts


def shown(page):
    return {title for title in ("Stoner", "Crash", "Kindred") if title in page}


def test_a_price_with_no_strip_draws_nothing_in_its_place(client, three_books):
    """A market with one price ever seen has no strip. The row printed the
    word "None" there, which S60 made likelier by letting new copies lead."""
    page = client.get("/").text

    assert "from $9" in page
    assert "None" not in page


def under_toggle(page):
    """The "Under limit" switch's opening tag, as a reader's tap finds it."""
    found = re.search(r'<button type="button" class="toggle"[^>]*>Under limit', page)
    assert found, "no Under limit switch"
    return found.group(0)


def test_under_limit_is_a_switch_without_a_count(client, three_books):
    """S69 (#217): a filter that is on or off is a switch, not a pair, and
    carries no count."""
    page = client.get("/").text

    toggle = under_toggle(page)
    assert 'aria-pressed="false"' in toggle
    assert shown(page) == {"Stoner", "Crash", "Kindred"}


def test_under_limit_shows_only_the_books_with_a_copy_under_their_limit(
    client, three_books
):
    page = client.get("/?show=under").text

    assert shown(page) == {"Stoner"}
    assert 'aria-pressed="true"' in under_toggle(page)


def test_the_switch_fetches_the_list_without_adding_history(client, three_books):
    page = client.get("/").text

    toggle = under_toggle(page)
    assert 'hx-get="/books/list?show=under"' in toggle
    assert 'hx-replace-url="/?show=under"' in toggle
    assert "hx-push-url" not in page
    assert shown(client.get("/books/list?show=under").text) == {"Stoner"}


def test_with_nothing_under_a_limit_the_switch_is_greyed_and_all_shows(
    client, monkeypatch, three_books
):
    from book_watch import standing

    monkeypatch.setattr(
        standing, "glance", lambda connection, book, **_: priced("over")
    )

    page = client.get("/?show=under").text

    assert shown(page) == {"Stoner", "Crash", "Kindred"}
    toggle = under_toggle(page)
    assert "disabled" in toggle
    assert 'aria-pressed="false"' in toggle


def test_with_a_book_under_its_limit_the_switch_is_not_greyed(client, three_books):
    assert "disabled" not in under_toggle(client.get("/").text)


# --- the order (S69, #217) ------------------------------------------------------


def priced_at(amount):
    """What `standing.glance` says of a book whose cheapest copy costs
    `amount`, or of a book with no price when `amount` is None."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from book_watch.ebay.search import Money
    from book_watch.standing import Glance, Headline, Market

    if amount is None:
        return Glance(checked=datetime.now(UTC), listed=0, uncertain=0, headline=None)
    price = Money(Decimal(amount), "USD")
    return Glance(
        checked=datetime.now(UTC),
        listed=1,
        uncertain=0,
        headline=Headline(
            market=Market(listed=1, seen=1, low=price, high=price),
            cheapest=price,
            verdict="no ceiling",
        ),
    )


@pytest.fixture
def three_prices(client, monkeypatch):
    """Added in this order: Stoner at $12, Crash at $5, Kindred with no price."""
    from book_watch import standing, wantlist

    amounts = {}
    with closing(client.app.state.connect()) as connection:
        for title, amount in (
            ("Stoner", "12.00"),
            ("Crash", "5.00"),
            ("Kindred", None),
        ):
            book = wantlist.add_identified(connection, title=title)
            amounts[book.id] = amount
        connection.commit()
    monkeypatch.setattr(
        standing, "glance", lambda connection, book, **_: priced_at(amounts[book.id])
    )
    return amounts


def order(page):
    """The books in the order a reader sees them."""
    return [
        title
        for title in re.findall(r'class="book-row-title"[^>]*>([^<]+)<', page)
        if title in ("Stoner", "Crash", "Kindred")
    ]


def test_the_list_is_newest_added_first_by_default(client, three_prices):
    page = client.get("/").text

    assert order(page) == ["Kindred", "Crash", "Stoner"]
    assert re.search(r'<b class="pair-option" aria-current="true"[^>]*>Added<', page)


def test_cheapest_goes_by_the_price_each_row_shows_and_unpriced_go_last(
    client, three_prices
):
    page = client.get("/?sort=cheapest").text

    assert order(page) == ["Crash", "Stoner", "Kindred"]
    assert re.search(r'<b class="pair-option" aria-current="true"[^>]*>Cheapest<', page)


def test_the_order_and_the_filter_keep_each_other(client, three_books):
    """Each choice keeps the other in the page address, so a book's page and
    going back, or a reload, show the list as it was."""
    page = client.get("/?show=under&sort=cheapest").text

    assert 'hx-replace-url="/?sort=cheapest"' in under_toggle(page)
    assert 'hx-replace-url="/?show=under"' in page  # Added, keeping the filter


def test_a_piece_of_the_list_keeps_the_order_of_the_page_it_came_from(
    client, three_prices
):
    """Deleting a book or the header asking for itself comes from another
    path, and reads the order from the page's own address."""
    crash = next(i for i, v in three_prices.items() if v == "5.00")

    page = client.delete(
        f"/books/{crash}",
        headers={"HX-Request": "true", "HX-Current-URL": "http://x/?sort=cheapest"},
    ).text

    assert order(page) == ["Stoner", "Kindred"]


def test_deleting_a_book_keeps_the_filter_on(client, three_books):
    crash = next(i for i, v in three_books.items() if v == "over")

    page = client.delete(
        f"/books/{crash}",
        headers={"HX-Request": "true", "HX-Current-URL": "http://x/?show=under"},
    ).text

    assert shown(page) == {"Stoner"}


def test_adding_a_book_shows_the_whole_list_with_the_new_book(
    client, catalog, three_books
):
    response = client.post(
        "/books",
        data={"isbn": "9780099448396", "title": "", "override": ""},
        headers={"HX-Request": "true", "HX-Current-URL": "http://x/?show=under"},
    )

    assert response.headers["HX-Replace-Url"] == "/"
    assert {"Stoner", "Crash", "Kindred"} <= shown(response.text)
    assert 'href="/book/4"' in response.text


def test_a_row_says_its_limit_or_that_there_is_none(client, three_books):
    """S61: where "$X over" was. An over price says nothing about how far."""
    from book_watch import wantlist

    stoner = next(i for i, v in three_books.items() if v == "under")
    with closing(client.app.state.connect()) as connection:
        wantlist.set_ceiling(connection, stoner, "10.00", "USD")
        connection.commit()

    page = client.get("/").text

    assert page.count("your limit: $10") == 1
    assert page.count("no limit set") == 2
    assert not re.search(r"\$[\d.]+ over", page)

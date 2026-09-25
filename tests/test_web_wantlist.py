"""Tests for the want-list screens, driven through the real templates."""

import dataclasses

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import db
from book_watch.config import DeletionEndpointConfig
from book_watch.openlibrary import Candidate, EditionIdentity, OpenLibraryUnavailable
from book_watch.web import wantlist as web_wantlist
from book_watch.web.app import create_app

DELETION_CONFIG = DeletionEndpointConfig(
    verification_token="a" * 32,
    endpoint_url="https://book-watch.fly.dev/ebay/deletion",
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


class FakeCatalogue:
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


def build_client(tmp_path, catalogue):
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
        web_wantlist.build_router(connect, catalogue, search=never_searches)
    )
    # So a test can set up a state the routes cannot reach on their own.
    app.state.connect = connect
    return TestClient(app)


@pytest.fixture
def catalogue():
    return FakeCatalogue()


@pytest.fixture
def client(tmp_path, catalogue):
    return build_client(tmp_path, catalogue)


def add(client, isbn, title="", override=""):
    return client.post(
        "/books", data={"isbn": isbn, "title": title, "override": override}
    )


def test_an_empty_list_says_so(client):
    page = client.get("/").text

    assert "Nothing on the list yet" in page


def test_a_book_is_added_and_appears_on_the_list(client):
    response = add(client, "9780099448396", "Crash")

    assert response.status_code == 200
    assert "Crash" in response.text
    assert "9780099448396" in response.text
    assert "Nothing on the list yet" not in response.text


def test_an_isbn10_is_stored_as_the_isbn13_of_the_same_book(client):
    """Otherwise the same book could be added twice under two spellings."""
    add(client, "0099448394")

    assert "9780099448396" in client.get("/").text


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


def test_the_catalogue_title_is_shown_rather_than_the_one_typed(client):
    """Decision 32, and the reason this slice touches the ISBN path at all.

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
    client = build_client(tmp_path, FakeCatalogue(unavailable=True))

    response = add(client, "9780099448396")

    assert response.status_code == 503
    assert "could not be reached" in response.text
    assert 'name="override"' in response.text


def test_an_override_asks_open_library_nothing(catalogue, client):
    """The person has already decided. Asking again would be noise on a service
    that asks for low volume."""
    add(client, "9781590171998", override="1")

    assert catalogue.asked == []


# --- adding by title --------------------------------------------------------


def find(client, title, author=""):
    return client.post("/books", data={"title": title, "author": author})


def test_a_title_search_offers_candidates_to_choose_from(tmp_path):
    client = build_client(tmp_path, FakeCatalogue(candidates=CANDIDATES))

    response = find(client, "stoner", "john williams")

    assert "Which one?" in response.text
    assert "Stoner" in response.text
    # The omnibus is in the list too, which is the point of choosing.
    assert "Collected Novels" in response.text
    assert "Nothing on the list yet" in response.text


def test_candidates_carry_enough_to_tell_them_apart(tmp_path):
    client = build_client(tmp_path, FakeCatalogue(candidates=CANDIDATES))

    page = find(client, "stoner").text

    assert "John Williams" in page
    assert "1965" in page
    assert "49 editions" in page


def test_picking_a_candidate_puts_it_on_the_list(tmp_path):
    client = build_client(tmp_path, FakeCatalogue(candidates=CANDIDATES))

    response = client.post(
        "/books/chosen",
        data={"title": "Stoner", "author": "John Williams", "work_id": "OL3511459W"},
    )

    assert response.status_code == 200
    assert "Stoner" in response.text
    assert "Nothing on the list yet" not in response.text


def test_a_title_search_finding_nothing_says_so_and_suggests_the_isbn(tmp_path):
    client = build_client(tmp_path, FakeCatalogue(candidates=[]))

    response = find(client, "a book that does not exist")

    assert response.status_code == 404
    assert "Nothing found" in response.text
    assert "by ISBN" in response.text


def test_a_title_search_sends_the_author_along(catalogue, client):
    catalogue.candidates = CANDIDATES
    find(client, "stoner", "john williams")

    assert catalogue.asked == [("stoner", "john williams")]


def test_open_library_being_down_during_a_search_says_so(tmp_path):
    client = build_client(tmp_path, FakeCatalogue(unavailable=True))

    response = find(client, "stoner")

    assert response.status_code == 503
    assert "could not be reached" in response.text
    # The escape hatch still exists while it is down.
    assert "ISBN" in response.text


def test_adding_a_book_costs_one_request(catalogue, client):
    """Decision 7: the ten to fifteen a book eventually costs are its listings'."""
    add(client, "9780099448396")

    assert len(catalogue.asked) == 1


def test_the_app_does_not_open_the_database_at_startup(monkeypatch):
    """Same rule as the eBay client: the compliance endpoint must start even
    when everything else is misconfigured (decision 24)."""

    def explode(*args, **kwargs):
        raise AssertionError("the database must not be opened at startup")

    monkeypatch.setattr(web_wantlist, "load_database_path", explode)

    app_client = TestClient(create_app(DELETION_CONFIG))

    assert app_client.get("/health").status_code == 200


# --- the tag that says work is outstanding ---------------------------------


def test_a_book_with_copies_nobody_has_examined_says_so(client):
    """The tag the page renders, not just the property behind it.

    Asserted here because it once did not render at all: the property was
    right, the template edit silently did not apply, and nothing failed.
    """
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute("UPDATE work SET copies_fetched_at = datetime('now')")
        connection.commit()

    assert "still digging" in client.get("/").text


def test_a_book_nobody_has_opened_does_not_claim_to_be_working(client):
    """No copies means nothing to dig through. The app does not advertise
    work it has not started."""
    add(client, "9780099448396", "Crash")

    assert "still digging" not in client.get("/").text


def test_a_finished_book_stops_saying_it(client):
    add(client, "9780099448396", "Crash")
    with client.app.state.connect() as connection:
        connection.execute(
            "UPDATE work SET copies_fetched_at = datetime('now'), "
            "enriched_at = datetime('now')"
        )
        connection.commit()

    assert "still digging" not in client.get("/").text


# --- covers -----------------------------------------------------------------
#
# Decision 56. The page points at Open Library's cover server; only the ids
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
    client = build_client(tmp_path, FakeCatalogue(candidates=with_cover))

    page = find(client, "stoner").text

    assert COVER_URL in page
    assert f'name="cover_id" value="{STONER_COVER}"' in page


def test_a_picked_book_shows_its_cover_for_no_further_request(tmp_path):
    catalogue = FakeCatalogue()
    client = build_client(tmp_path, catalogue)

    page = pick(client, str(STONER_COVER)).text

    assert COVER_URL in page
    assert catalogue.asked == []


def test_a_picked_book_open_library_has_no_cover_for_shows_the_placeholder(tmp_path):
    client = build_client(tmp_path, FakeCatalogue())

    page = pick(client).text

    assert 'class="cover-name">Stoner<' in page
    # Nothing to load: Open Library already said so, and asking again on
    # every view would be asking for an answer we have.
    assert "/cover" not in page.split('id="want-list"')[1]
    assert "<img" not in page.split('id="want-list"')[1]


def test_a_book_added_by_number_shows_its_editions_cover(tmp_path):
    crash = dataclasses.replace(CRASH, cover_id=240726)
    catalogue = FakeCatalogue(identities={CRASH.isbn: crash})
    client = build_client(tmp_path, catalogue)

    page = add(client, CRASH.isbn).text

    assert "b/id/240726-M.jpg" in page
    assert len(catalogue.asked) == 1


def test_a_book_added_by_number_with_no_edition_cover_asks_later(tmp_path):
    """The work's cover is still unknown, and finding out is not worth a wait."""
    catalogue = FakeCatalogue()
    client = build_client(tmp_path, catalogue)

    page = add(client, CRASH.isbn).text

    assert 'src="/books/1/cover"' in page
    assert catalogue.asked == [CRASH.isbn]


def test_rendering_the_list_asks_open_library_nothing(tmp_path):
    catalogue = FakeCatalogue()
    client = build_client(tmp_path, catalogue)
    add(client, CRASH.isbn)
    pick(client)
    before = list(catalogue.asked)

    client.get("/")

    assert catalogue.asked == before


def test_the_cover_route_learns_the_cover_once_and_sends_the_browser_there(tmp_path):
    catalogue = FakeCatalogue(work_covers={CRASH.work_id: 240726})
    client = build_client(tmp_path, catalogue)
    add(client, CRASH.isbn)

    first = client.get("/books/1/cover", follow_redirects=False)
    second = client.get("/books/1/cover", follow_redirects=False)

    assert first.status_code == second.status_code == 302
    assert first.headers["location"].endswith("/b/id/240726-M.jpg?default=false")
    assert catalogue.asked.count(("cover", CRASH.work_id)) == 1
    # And the list now points there itself, so the route is not needed again.
    assert "b/id/240726-M.jpg" in client.get("/").text


def test_no_cover_is_a_404_and_the_list_stops_asking(tmp_path):
    client = build_client(tmp_path, FakeCatalogue())
    add(client, CRASH.isbn)

    response = client.get("/books/1/cover", follow_redirects=False)

    assert response.status_code == 404
    assert 'src="/books/1/cover"' not in client.get("/").text


def test_open_library_being_down_leaves_the_cover_to_be_asked_for_next_time(tmp_path):
    catalogue = FakeCatalogue(work_covers={CRASH.work_id: 240726})
    client = build_client(tmp_path, catalogue)
    add(client, CRASH.isbn)

    catalogue.unavailable = True
    assert client.get("/books/1/cover", follow_redirects=False).status_code == 404
    catalogue.unavailable = False

    assert client.get("/books/1/cover", follow_redirects=False).status_code == 302


def test_a_cover_for_a_book_that_is_not_there_is_a_404(client):
    assert client.get("/books/99/cover").status_code == 404


def test_the_list_credits_open_library_for_its_covers(tmp_path):
    client = build_client(tmp_path, FakeCatalogue())

    page = pick(client).text

    assert 'href="https://openlibrary.org"' in page

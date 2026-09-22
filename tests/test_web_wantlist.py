"""Tests for the want-list screens, driven through the real templates."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import db
from book_watch.config import DeletionEndpointConfig
from book_watch.web import wantlist as web_wantlist
from book_watch.web.app import create_app

DELETION_CONFIG = DeletionEndpointConfig(
    verification_token="a" * 32,
    endpoint_url="https://book-watch.fly.dev/ebay/deletion",
)


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    app = FastAPI()
    app.include_router(web_wantlist.build_router(connect))
    return TestClient(app)


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
    assert "Enter an ISBN" in response.text


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
    add(client, "9780099448396", "<script>alert('xss')</script>")
    page = client.get("/").text

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_the_app_does_not_open_the_database_at_startup(monkeypatch):
    """Same rule as the eBay client: the compliance endpoint must start even
    when everything else is misconfigured (decision 24)."""

    def explode(*args, **kwargs):
        raise AssertionError("the database must not be opened at startup")

    monkeypatch.setattr(web_wantlist, "load_database_path", explode)

    app_client = TestClient(create_app(DELETION_CONFIG))

    assert app_client.get("/health").status_code == 200

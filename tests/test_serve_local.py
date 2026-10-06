"""The local app used for screenshots makes no request (M14 learnings)."""

import sys
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from book_watch import db, wantlist

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import serve_local  # noqa: E402


@pytest.fixture
def local_client(tmp_path, monkeypatch):
    path = tmp_path / "local.db"
    monkeypatch.setenv("BOOK_WATCH_DB_PATH", str(path))
    monkeypatch.setattr(
        httpx.HTTPTransport, "handle_request", httpx.HTTPTransport.handle_request
    )  # Restored after the test, whatever serve_local patched it to.
    with closing(db.connect(path)) as connection:
        db.migrate(connection)
        wantlist.add(connection, "9780099448396", "Crash")
        connection.commit()
    return TestClient(serve_local.app())


def test_a_book_page_that_would_search_ebay_opens_without_a_request(local_client):
    """Never searched, so the real app would search eBay here."""
    page = local_client.get("/book/1")

    assert page.status_code == 200
    assert "Crash" in page.text


def test_the_want_list_opens(local_client):
    assert local_client.get("/").status_code == 200


def test_any_request_that_tries_to_leave_is_refused(local_client):
    with pytest.raises(serve_local.RefusedRequest, match="makes no requests"):
        httpx.get("https://www.ebay.com/")

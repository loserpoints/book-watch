"""Tests for the log lines in docs/rules/monitoring.md.

Each outside service writes one `call` line however a call ends, every line
names what started its work and which book it is about, and no line holds a
key, a token or an address.
"""

import logging
import threading
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import abebooks, alerts, daily, db, monitoring, pages, wantlist
from book_watch.config import AlertConfig, EbayCredentials
from book_watch.ebay.auth import PUBLIC_DATA_SCOPE, EbayTokenProvider
from book_watch.ebay.detail import ItemDetailClient
from book_watch.ebay.errors import EbayError
from book_watch.ebay.search import BrowseClient, Listing, Money
from book_watch.openlibrary import OpenLibraryClient
from book_watch.openlibrary.budget import BudgetExhausted
from book_watch.openlibrary.errors import OpenLibraryUnavailable
from book_watch.web import listings as listings_module
from book_watch.web import wantlist as web_wantlist
from book_watch.web.page_lines import PageLines

SECRET_ID = "an-app-id-SECRET"
SECRET_CERT = "a-cert-id-SECRET"
SECRET_TOKEN = "v^1.1#i^1#fake-bearer-SECRET"
RESEND_KEY = "re_SECRETKEY123"
ADDRESS = "reader@example.com"


@pytest.fixture
def lines(caplog):
    """Every line written while the test runs, as text."""
    caplog.set_level(logging.INFO, logger="book_watch")

    def written(event: str | None = None) -> list[str]:
        found = [
            record.getMessage()
            for record in caplog.records
            if getattr(record, "logfmt", False)
        ]
        if event is None:
            return found
        return [line for line in found if line.startswith(f"event={event} ")]

    return written


# --- the line itself ---------------------------------------------------------


def test_a_line_keeps_its_order_quotes_spaces_and_leaves_out_empty_fields():
    line = monitoring.line(
        "call",
        service="abebooks",
        title="The Count of Monte Cristo",
        reason=None,
        full=False,
        note='said "no"',
    )

    assert line == (
        'event=call service=abebooks title="The Count of Monte Cristo" '
        'full=no note="said \\"no\\""'
    )


def test_every_line_starts_with_its_level_whoever_wrote_it():
    formatter = monitoring.Logfmt()
    ours = logging.LogRecord(
        "book_watch", logging.WARNING, "", 0, "event=call service=ebay", None, None
    )
    ours.logfmt = True
    theirs = logging.LogRecord(
        "uvicorn.error", logging.INFO, "", 0, "Started server process", None, None
    )

    assert formatter.format(ours) == "level=warn event=call service=ebay"
    assert formatter.format(theirs) == (
        'level=info event=log logger=uvicorn.error msg="Started server process"'
    )


# --- why a call failed -------------------------------------------------------


def a_call_that_raises(exc, status=None):
    with pytest.raises(type(exc)), monitoring.call("ebay", "search"):
        if status is not None:
            monitoring.call_answered(status)
        raise exc


@pytest.mark.parametrize(
    ("exc", "status", "outcome", "reason"),
    [
        (httpx.ReadTimeout("slow"), None, "failed", "timeout"),
        (httpx.ConnectError("no route"), None, "failed", "down"),
        (EbayError("eBay said 503"), 503, "failed", "down"),
        (EbayError("eBay said 429"), 429, "failed", "refused"),
        (ValueError("not JSON"), 200, "failed", "unreadable"),
        (BudgetExhausted("500 in a day"), None, "skipped", "limit"),
        (pages.RefusedPath("robots.txt disallows /x"), None, "skipped", "blocked"),
    ],
)
def test_a_failed_call_names_its_reason(lines, exc, status, outcome, reason):
    a_call_that_raises(exc, status)

    [line] = lines("call")
    assert f"outcome={outcome} reason={reason}" in line


def test_a_call_that_returns_is_ok_with_its_status_and_time(lines):
    with monitoring.call("openlibrary", "isbn"):
        monitoring.call_answered(200)

    [line] = lines("call")
    assert line.startswith(
        "event=call service=openlibrary endpoint=isbn trigger=unknown "
        "outcome=ok status=200 ms="
    )


# --- each service ------------------------------------------------------------


def a_token_provider(status=200):
    def handler(request):
        if status != 200:
            return httpx.Response(status, json={"error": "invalid_client"})
        return httpx.Response(
            200,
            json={
                "access_token": SECRET_TOKEN,
                "expires_in": 7200,
                "token_type": "Application Access Token",
                "scope": PUBLIC_DATA_SCOPE,
            },
        )

    return EbayTokenProvider(
        EbayCredentials(client_id=SECRET_ID, client_secret=SECRET_CERT),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_an_ebay_search_writes_its_token_and_its_search(lines):
    def handler(request):
        return httpx.Response(200, json={"total": 0, "itemSummaries": []})

    browse = BrowseClient(
        a_token_provider(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with monitoring.started_by("open"), monitoring.about(12, "Stoner"):
        browse.search("stoner williams")

    token, search = lines("call")
    assert "service=ebay endpoint=token trigger=open" in token
    assert search.startswith(
        "event=call service=ebay endpoint=search trigger=open book=12 title=Stoner "
        "outcome=empty status=200 results=0 ms="
    )


def test_a_failed_ebay_search_says_what_ebay_answered(lines):
    def handler(request):
        return httpx.Response(500, json={"errors": [{"message": "Internal error"}]})

    browse = BrowseClient(
        a_token_provider(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(EbayError):
        browse.search("stoner")

    [_, search] = lines("call")
    assert "endpoint=search" in search
    assert "outcome=failed reason=down status=500" in search


def test_a_check_takes_the_reason_of_the_call_that_failed_under_it(lines):
    with (
        pytest.raises(EbayError),
        monitoring.check("ebay"),
        monitoring.call("ebay", "search"),
    ):
        monitoring.call_answered(503)
        raise EbayError("eBay said 503")

    [check] = lines("check")
    assert "outcome=failed reason=down" in check


def test_an_ebay_item_that_has_gone_is_empty(lines):
    def handler(request):
        return httpx.Response(404)

    detail = ItemDetailClient(
        a_token_provider(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    detail.declared_by("v1|1|0")

    assert (
        "endpoint=item trigger=unknown outcome=empty status=404" in (lines("call")[-1])
    )


class _Budget:
    def __init__(self, full=False):
        self.full = full

    def spend(self, endpoint):
        if self.full:
            raise BudgetExhausted("500 Open Library requests. Nothing has been sent.")


def an_open_library(handler, budget=None):
    return OpenLibraryClient(
        budget or _Budget(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        min_interval_seconds=0,
    )


def test_an_open_library_lookup_names_its_number(lines):
    library = an_open_library(lambda request: httpx.Response(503, text="down"))

    with pytest.raises(OpenLibraryUnavailable):
        library.identify_isbn("9780099448396")

    [line] = lines("call")
    assert line.startswith(
        "event=call service=openlibrary endpoint=isbn trigger=unknown "
        "outcome=failed reason=down status=503 isbn=9780099448396 ms="
    )


def test_an_open_library_call_past_the_limit_is_skipped(lines):
    library = an_open_library(
        lambda request: pytest.fail("asked past the limit"), _Budget(full=True)
    )

    with pytest.raises(BudgetExhausted):
        library.search_works("Stoner")

    [line] = lines("call")
    assert "endpoint=search" in line
    assert "outcome=skipped reason=limit" in line


def test_an_abebooks_page_it_cant_read_fails_as_unreadable(lines, monkeypatch):
    monkeypatch.setattr(pages, "fetch", lambda url: (200, "<html></html>"))
    monkeypatch.setattr(abebooks, "SPACING_SECONDS", 0)

    with pytest.raises(abebooks.AbeBooksError):
        abebooks.read("https://www.abebooks.com/book-search/title/stoner/")

    [line] = lines("call")
    assert line.startswith(
        "event=call service=abebooks endpoint=page trigger=unknown "
        "outcome=failed reason=unreadable status=200 "
        "url=https://www.abebooks.com/book-search/title/stoner/ ms="
    )


def test_a_failed_email_keeps_the_key_and_the_address_out_of_its_line(lines):
    def post(url, **kwargs):
        return httpx.Response(
            403,
            text=f"You can only send testing emails to your own address ({ADDRESS})."
            f" Key {RESEND_KEY} is restricted.",
        )

    with pytest.raises(alerts.AlertError):
        alerts.send(AlertConfig(api_key=RESEND_KEY, to=ADDRESS), "s", "h", "t", post)

    [line] = lines("call")
    assert "service=resend endpoint=send" in line
    assert "outcome=failed reason=refused status=403" in line
    assert ADDRESS not in line
    assert RESEND_KEY not in line


def test_no_line_holds_an_ebay_key_or_token(lines):
    def handler(request):
        # A body that echoes what was sent, as an error page might.
        return httpx.Response(401, text=str(dict(request.headers)))

    browse = BrowseClient(
        a_token_provider(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(EbayError):
        browse.search("stoner")
    with pytest.raises(EbayError):
        a_token_provider(status=401).token()

    text = "\n".join(lines())
    assert "Bearer <token>'" in text
    # Any piece of a secret, not only the whole of it.
    assert "SECRET" not in text


# --- where the trigger comes from ----------------------------------------------


def test_work_handed_to_a_thread_keeps_its_trigger_and_book(lines):
    def in_a_thread():
        with monitoring.call("ebay", "item"):
            pass

    with monitoring.started_by("check"), monitoring.about(3, "Crash"):
        carried = monitoring.carried(in_a_thread)
    thread = threading.Thread(target=carried)
    thread.start()
    thread.join()

    assert "trigger=check book=3 title=Crash" in lines("call")[0]


BOOK = "9780099448396"


def a_listing(n=0):
    return Listing(
        item_id=f"v1|{n}|0",
        title="Crash a fine copy",
        price=Money(Decimal("8.00"), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        condition="Good",
        seller="seller",
        shipping_cost=Money(Decimal("0.00"), "USD"),
        thumbnail_url=None,
        listing_date=datetime(2026, 9, 1, tzinfo=UTC),
    )


@pytest.fixture
def connect(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    with closing(connect()) as connection:
        wantlist.add(connection, BOOK, "Crash")
        connection.commit()
    return connect


def searching(query, limit, **_):
    # As the real client does, a call line for the search itself.
    with monitoring.call("ebay", "search"):
        return [a_listing(n) for n in range(3)]


def examining(work_id):
    with monitoring.call("openlibrary", "isbn"):
        pass


def an_app(connect):
    app = FastAPI()
    app.include_router(
        listings_module.build_router(searching, connect, enrich=examining)
    )
    app.include_router(
        web_wantlist.build_router(connect, None, search=searching, enrich=examining)
    )
    app.add_middleware(PageLines)
    return TestClient(app)


def test_opening_a_book_names_open_on_its_check_and_its_examination(connect, lines):
    an_app(connect).get("/book/1")

    [search] = [line for line in lines("call") if "endpoint=search" in line]
    [lookup] = [line for line in lines("call") if "endpoint=isbn" in line]
    [check] = lines("check")
    assert "trigger=open book=1 title=Crash" in search
    assert check.startswith(
        "event=check marketplace=ebay trigger=open book=1 title=Crash "
        "outcome=ok copies=3 new=3 full=no ms="
    )
    # Run as a background task after the page was sent.
    assert "trigger=open book=1 title=Crash" in lookup


def test_the_checked_chip_names_recheck(connect, lines):
    an_app(connect).get("/book/1?refresh=1", follow_redirects=False)

    assert "trigger=recheck book=1" in lines("check")[0]


def test_the_check_button_names_check_and_writes_the_action(connect, lines):
    client = an_app(connect)
    client.get("/books/check?force=1")
    client.get("/books/1/check?force=1")

    assert lines("action") == ["event=action name=check all=yes books=1"]
    assert "trigger=check book=1 title=Crash" in lines("check")[0]


def test_a_requests_trigger_ends_with_it(connect, lines):
    an_app(connect).get("/book/1")

    assert monitoring.trigger() == "unknown"


def test_each_request_writes_a_page_line_but_the_health_check(connect, lines):
    client = an_app(connect)
    client.get("/")
    client.get("/health")

    [line] = lines("page")
    assert line.startswith("event=page path=/ status=200 ms=")


def test_the_daily_check_names_daily_on_every_line_beneath_it(connect, lines):
    def emailing():
        return 2

    daily.run(connect, searching, examining, lambda: 0, notify=emailing)

    assert lines("job")[0] == "event=job name=daily phase=start trigger=daily"
    assert lines("job")[-1].startswith(
        "event=job name=daily phase=end trigger=daily outcome=ok books=1 failed=0"
    )
    assert all("trigger=daily" in line for line in lines())
    assert "book=1 title=Crash" in lines("check")[0]
    assert any(
        line.startswith("event=job name=email phase=end trigger=daily outcome=ok")
        and "copies=2" in line
        for line in lines("job")
    )


def test_a_daily_check_that_crashes_ends_its_job_with_the_traceback(connect, caplog):
    caplog.set_level(logging.INFO, logger="book_watch")

    def crashing(query, limit, **_):
        raise RuntimeError("something nobody planned for")

    with pytest.raises(RuntimeError):
        daily.run(connect, crashing, examining, lambda: 0)

    [end] = [
        record
        for record in caplog.records
        if record.getMessage().startswith("event=job name=daily phase=end")
    ]
    assert end.levelname == "ERROR"
    assert "outcome=failed" in end.getMessage()
    assert end.exc_info is not None


def test_an_email_with_a_setting_missing_is_skipped_for_setup(connect, lines):
    daily.run(connect, searching, examining, lambda: 0, notify=lambda: None)

    [end] = [line for line in lines("job") if "name=email phase=end" in line]
    assert "outcome=skipped reason=setup" in end


def test_a_trigger_set_in_one_request_never_reaches_the_next(connect):
    """Sync handlers share a pool of worker threads. Each must start from the
    request's own context, or a trigger would carry over to the next request
    run on the same thread."""
    app = FastAPI()

    @app.get("/sets")
    def sets() -> int:
        monitoring.handling("open", 1, "Crash")
        return threading.get_ident()

    @app.get("/reads")
    def reads() -> list:
        return [monitoring.trigger(), threading.get_ident()]

    client = TestClient(app)
    shared = 0
    for _ in range(20):
        setter = client.get("/sets").json()
        trigger, reader = client.get("/reads").json()
        assert trigger == "unknown"
        shared += setter == reader
    # Only proves anything if a thread was reused.
    assert shared > 0

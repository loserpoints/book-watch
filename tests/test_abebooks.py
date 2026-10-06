"""AbeBooks copies on a book's page, in the daily check and the email (S66).

No network: every test passes a reader that returns a page it made up, and
conftest refuses any real request. The parser itself is tested against a real
page in `test_pages.py`.
"""

import html
import logging
import re
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch import abebooks, alerts, copies, daily, db, pages, sweeps, wantlist
from book_watch.ebay.search import Listing, Money, Results
from book_watch.web import listings as listings_module
from book_watch.web import wantlist as web_wantlist

CRASH = "9780099448396"


def a_copy(n: int = 1, **overrides) -> pages.Copy:
    fields = {
        "listing_id": f"3108127700{n}",
        "price": Decimal(f"{4 + n}.00"),
        "shipping": Decimal("4.00"),
        "first_edition": False,
        "isbn": CRASH,
        "title": "Crash",
        "url": f"https://www.abebooks.com/servlet/BookDetailsPL?bi=3108127700{n}",
        "author": "J. G. Ballard",
        "publisher": "Vintage",
        "published": "2004",
        "binding": "Softcover",
        "condition": "Used - Good",
        "seller": "Better World Books",
        "location": "Mishawaka, IN, U.S.A.",
        "photo": "https://pictures.abebooks.com/isbn/9780099448396-us-300.jpg",
        "note": "Clean, average condition.",
    }
    fields.update(overrides)
    return pages.Copy(**fields)


def a_page(*found: pages.Copy, count: int | None = None) -> pages.Page:
    return pages.Page(
        result_count=len(found) if count is None else count, copies=list(found)
    )


class FakeReader:
    """Answers each read with the next page, or raises the next error."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.urls: list[str] = []

    def __call__(self, url: str) -> pages.Page:
        self.urls.append(url)
        answer = self.answers[0] if len(self.answers) == 1 else self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def connect(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    return connect


def add_crash(connect) -> wantlist.Entry:
    """Crash by its ISBN, so its copies grade against a known edition."""
    with closing(connect()) as connection:
        entry = wantlist.add(connection, CRASH, "Crash: A Novel")
        connection.execute(
            "UPDATE work SET author = 'J. G. Ballard' WHERE id = ?", (entry.work_id,)
        )
        connection.commit()
        return wantlist.get(connection, entry.id)


# --- writing the search ------------------------------------------------------


def test_the_search_is_written_as_abebooks_reads_it():
    assert abebooks.search_url("Crash: A Novel", "J. G. Ballard", None) == (
        "https://www.abebooks.com/book-search/title/crash/author/j-g-ballard/"
    )
    assert abebooks.search_url("Cien años de soledad", None, None) == (
        "https://www.abebooks.com/book-search/title/cien-anos-de-soledad/author/_/"
    )


def test_a_book_known_only_by_its_isbn_is_read_from_that_isbns_page():
    assert abebooks.search_url(None, None, "978-0-09-944839-6") == (
        "https://www.abebooks.com/book-search/isbn/9780099448396/used/"
    )
    assert abebooks.search_url(None, None, "not a number") is None


def test_every_url_it_writes_is_one_robots_txt_allows():
    for url in (
        abebooks.search_url("Crash", "J. G. Ballard", None),
        abebooks.search_url(None, None, CRASH),
    ):
        pages.check_url(url)  # Raises on a disallowed path.


# --- the page's shape --------------------------------------------------------


@pytest.mark.parametrize(
    ("page", "why"),
    [
        (pages.Page(result_count=None, challenged=True), "bot challenge"),
        (pages.Page(result_count=None, copies=[a_copy()]), "without a count"),
        (a_page(a_copy(grouped=True)), "grouped"),
        (a_page(a_copy(shipping=None)), "without a price"),
        (a_page(a_copy(url=None)), "without a price, an id or a link"),
        (a_page(a_copy(2), a_copy(1)), "not cheapest first"),
    ],
)
def test_a_page_in_a_shape_never_seen_fails_rather_than_being_guessed_at(page, why):
    with pytest.raises(abebooks.AbeBooksError, match=why):
        abebooks.checked(page)


def test_an_empty_page_is_an_ordinary_answer():
    assert abebooks.checked(pages.Page(result_count=None)).copies == []


def test_a_count_over_the_page_is_fine():
    assert abebooks.checked(a_page(a_copy(), count=1500)).result_count == 1500


# --- storing a check ---------------------------------------------------------


def test_a_check_stores_the_copies_for_both_views(connect):
    entry = add_crash(connect)
    reader = FakeReader(
        a_page(
            a_copy(1),
            a_copy(2, condition="Used", location="London, United Kingdom"),
        )
    )
    with closing(connect()) as connection:
        outcome = abebooks.check_book(connection, entry, reader)
        rows = connection.execute(
            "SELECT item_id, condition_id, located_in, url, thumbnail FROM copy "
            "WHERE marketplace = 'abebooks' ORDER BY item_id"
        ).fetchall()
        scopes = connection.execute(
            "SELECT scope, COUNT(*) FROM copy_seen WHERE marketplace = 'abebooks' "
            "GROUP BY scope ORDER BY scope"
        ).fetchall()
        declared = connection.execute(
            "SELECT isbn, publisher, condition_note FROM listing_declaration "
            "WHERE marketplace = 'abebooks' AND item_id = '31081277001'"
        ).fetchone()

    assert outcome == "ok"
    assert reader.urls == [
        "https://www.abebooks.com/book-search/title/crash/author/j-g-ballard/"
    ]
    assert [tuple(row) for row in rows] == [
        (
            "31081277001",
            "5000",
            "US",
            a_copy(1).url,
            a_copy(1).photo,
        ),
        # A bare "Used" is eBay's generic Used, and abroad is never US-only.
        ("31081277002", "3000", "GB", a_copy(2).url, a_copy(2).photo),
    ]
    assert [tuple(row) for row in scopes] == [("everywhere", 2), ("us", 1)]
    assert tuple(declared) == (CRASH, "Vintage", "Clean, average condition.")


def test_new_copies_set_the_book_digging_again(connect):
    entry = add_crash(connect)
    with closing(connect()) as connection:
        connection.execute(
            "UPDATE work SET enriched_at = datetime('now') WHERE id = ?",
            (entry.work_id,),
        )
        abebooks.check_book(connection, entry, FakeReader(a_page(a_copy())))
        book = wantlist.get(connection, entry.id)

    assert book.being_enriched


def test_a_failed_check_leaves_ebays_copies_alone_and_logs_why(connect, caplog):
    entry = add_crash(connect)
    ebay = Listing(
        item_id="v1|1|0",
        title="Crash Ballard",
        price=Money(Decimal("9.00"), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        located_in="US",
    )
    with closing(connect()) as connection:
        sweeps.store(connection, entry.work_id, Results([ebay], total=1), asked_for=50)
        connection.commit()
        with caplog.at_level(logging.WARNING, logger="book_watch.abebooks"):
            outcome = abebooks.check_book(
                connection,
                entry,
                FakeReader(abebooks.AbeBooksError("grouped rows")),
            )
        stored = connection.execute(
            "SELECT marketplace FROM copy WHERE work_id = ?", (entry.work_id,)
        ).fetchall()
        abebooks_sweeps = connection.execute(
            "SELECT COUNT(*) FROM sweep WHERE marketplace = 'abebooks'"
        ).fetchone()[0]
        last = abebooks.last_outcome(connection, entry.work_id)

    assert outcome == "failed"
    assert [row[0] for row in stored] == ["ebay"]
    assert abebooks_sweeps == 0
    assert last == "failed"
    assert "grouped rows" in caplog.text


def test_a_failed_check_keeps_the_last_good_copies_listed(connect):
    entry = add_crash(connect)
    with closing(connect()) as connection:
        abebooks.check_book(connection, entry, FakeReader(a_page(a_copy())))
        abebooks.check_book(
            connection,
            entry,
            FakeReader(abebooks.AbeBooksError("bot challenge")),
            force=True,
        )
        listed = copies.for_entry(connection, entry, scope="everywhere")

    assert [copy.key for copy in listed] == [("abebooks", "31081277001")]


def test_the_hour_gate_holds_whatever_the_last_outcome(connect):
    """A failed page is not read again on every visit."""
    entry = add_crash(connect)
    reader = FakeReader(abebooks.AbeBooksError("status 503"))
    with closing(connect()) as connection:
        abebooks.check_book(connection, entry, reader)
        again = abebooks.check_book(connection, entry, reader)
        forced = abebooks.check_book(connection, entry, reader, force=True)
        connection.execute(
            "UPDATE marketplace_check SET checked_at = datetime('now', '-61 minutes')"
        )
        later = abebooks.check_book(connection, entry, reader)

    assert again is None
    assert forced == "failed"
    assert later == "failed"
    assert len(reader.urls) == 3


def test_no_reader_reads_nothing(connect):
    entry = add_crash(connect)
    with closing(connect()) as connection:
        assert abebooks.check_book(connection, entry, None) is None
        assert abebooks.last_outcome(connection, entry.work_id) is None


# --- the daily check ---------------------------------------------------------


def test_the_daily_check_reads_each_book_before_examining_it(connect):
    add_crash(connect)
    order = []

    def search(query, limit, **_):
        order.append("ebay")
        return Results([], total=0)

    def read(url):
        order.append("abebooks")
        return a_page(a_copy())

    daily.run(
        connect,
        search,
        lambda work_id: order.append("examine"),
        lambda: 0,
        read_abebooks=read,
    )

    assert order == ["ebay", "abebooks", "examine"]


def test_the_daily_check_carries_on_when_abebooks_fails(connect):
    add_crash(connect)
    examined = []
    daily.run(
        connect,
        lambda query, limit, **_: Results([], total=0),
        examined.append,
        lambda: 0,
        read_abebooks=FakeReader(abebooks.AbeBooksError("grouped rows")),
    )
    with closing(connect()) as connection:
        outcome = connection.execute("SELECT outcome FROM daily_run").fetchone()[0]

    # The run went fine: eBay was searched. The book's page says the rest.
    assert outcome == "ok"


# --- the email ---------------------------------------------------------------


def test_the_email_says_which_marketplace_a_copy_is_on(connect):
    entry = add_crash(connect)
    with closing(connect()) as connection:
        wantlist.set_ceiling(connection, entry.id, "20", "USD")
        abebooks.check_book(connection, entry, FakeReader(a_page(a_copy())))
        [copy] = copies.for_entry(connection, entry, scope="everywhere")
        entry = wantlist.get(connection, entry.id)

    _, body_html, body_text = alerts.compose([alerts.Alert(entry, copy, None)])

    assert "Used - Good · on AbeBooks" in body_text
    assert a_copy().url in body_html


# --- the book's page and the want list -------------------------------------


def visible(page: str) -> str:
    text = re.sub(r"(?s)<(script|style).*?</\1>", " ", page)
    text = re.sub(r'(?s)<span class="sr-only">.*?</span>', " ", text)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))


@pytest.fixture
def client_for(connect):
    def make(reader, search=None):
        app = FastAPI()
        run_search = search or (lambda query, limit, **_: Results([], total=0))
        app.include_router(
            listings_module.build_router(
                run_search, connect, lambda work_id: None, read_abebooks=reader
            )
        )
        app.include_router(
            web_wantlist.build_router(
                connect,
                search=run_search,
                enrich=lambda work_id: None,
                read_abebooks=reader,
            )
        )
        return TestClient(app)

    return make


def test_the_book_page_shows_abebooks_copies_with_their_banner(connect, client_for):
    entry = add_crash(connect)
    ebay = Listing(
        item_id="v1|1|0",
        title=f"Crash J. G. Ballard {CRASH}",
        price=Money(Decimal("30.00"), "USD"),
        item_web_url="https://www.ebay.com/itm/1",
        located_in="US",
        thumbnail_url="https://i.ebayimg.com/1.jpg",
        listing_date=datetime(2026, 9, 1, tzinfo=UTC),
    )
    client = client_for(
        FakeReader(a_page(a_copy())),
        search=lambda query, limit, **_: Results([ebay], total=1),
    )

    with closing(connect()) as connection:
        connection.execute(
            "INSERT INTO listing_declaration (marketplace, item_id, isbn) "
            "VALUES ('ebay', 'v1|1|0', ?)",
            (CRASH,),
        )
        connection.commit()

    page = client.get(f"/book/{entry.id}?everywhere=1").text

    assert a_copy().url in page
    assert '<span class="copy-market" aria-hidden="true">AbeBooks</span>' in page
    assert '<span class="copy-market" aria-hidden="true">eBay</span>' in page
    assert '<span class="sr-only">On AbeBooks.</span>' in page
    assert a_copy().photo in page
    assert "AbeBooks check failed" not in page


def test_a_failed_check_is_one_line_on_the_book_page(connect, client_for):
    entry = add_crash(connect)
    client = client_for(FakeReader(abebooks.AbeBooksError("bot challenge")))

    page = client.get(f"/book/{entry.id}").text

    assert "AbeBooks check failed" in visible(page)
    assert "bot challenge" not in page


def test_an_empty_result_links_to_the_search_that_found_nothing(connect, client_for):
    entry = add_crash(connect)
    client = client_for(FakeReader(a_page()))

    page = client.get(f"/book/{entry.id}").text

    assert "No copies on AbeBooks" in visible(page)
    assert (
        'href="https://www.abebooks.com/book-search/title/crash/author/j-g-ballard/"'
        in page
    )


def test_opening_a_book_again_within_the_hour_does_not_read_again(connect, client_for):
    entry = add_crash(connect)
    reader = FakeReader(a_page(a_copy()))
    client = client_for(reader)

    client.get(f"/book/{entry.id}")
    client.get(f"/book/{entry.id}")
    client.get(f"/book/{entry.id}?refresh=1")

    # The second visit is inside the hour; checking again ignores it.
    assert len(reader.urls) == 2


def test_update_reads_abebooks_too(connect, client_for):
    entry = add_crash(connect)
    reader = FakeReader(a_page(a_copy()))
    client = client_for(reader)

    client.get(f"/books/{entry.id}/check")

    assert len(reader.urls) == 1

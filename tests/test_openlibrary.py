"""Tests for the Open Library client and the notebook it writes to.

Everything here but the final test runs against `httpx.MockTransport`, so CI
makes no request to a non-profit that has asked not to be used as a backend
(decision 7). The recorded bodies are real responses, kept from the S6
measurement, trimmed to the fields this app reads.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from book_watch import db
from book_watch.openlibrary import (
    Candidate,
    OpenLibraryClient,
    OpenLibraryUnavailable,
    Resolver,
)
from book_watch.openlibrary.client import USER_AGENT

# --- recorded from Open Library during S6 -----------------------------------

STONER = {
    "title": "Stoner",
    "works": [{"key": "/works/OL3511459W"}],
    "publishers": ["New York Review Books"],
    "publish_date": "2006",
    "physical_format": "Trade Paperback",
}

#: The target *Crash* edition, which Open Library holds with no format at all.
#: This is why Open Library cannot be the only source of edition attributes.
CRASH = {
    "title": "Crash",
    "works": [{"key": "/works/OL2745977W"}],
    "publishers": ["Farrar, Straus and Giroux"],
    "publish_date": "April 1, 1994",
}

#: The omnibus. Three listings in S6's sample declared this number; their
#: titles say "Stoner" and their author is John Williams, so every eBay signal
#: admits them. Only this lookup rejects them.
OMNIBUS = {
    "title": "John Williams : Collected Novels",
    "works": [{"key": "/works/OL26589081W"}],
    "publishers": ["Library of America, The"],
    "publish_date": "2021",
}

SEARCH = {
    "numFound": 793,
    "docs": [
        {
            "key": "/works/OL66554W",
            "title": "Pride and Prejudice",
            "author_name": ["Jane Austen"],
            "first_publish_year": 1813,
            "edition_count": 4042,
        },
        {
            "key": "/works/OL66597W",
            "title": "Novels (Pride and Prejudice / Sense and Sensibility)",
            "author_name": ["Jane Austen"],
            "first_publish_year": 1949,
            "edition_count": 28,
        },
    ],
}


def build_client(handler, **kwargs) -> OpenLibraryClient:
    """A client wired to a fake Open Library, with the pause disabled."""
    kwargs.setdefault("min_interval_seconds", 0)
    return OpenLibraryClient(
        client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs
    )


def responds_with(payload, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handler


# --- identifying a number ---------------------------------------------------


def test_identifies_what_a_number_is():
    client = build_client(responds_with(STONER))

    identity = client.identify_isbn("9781590171998")

    assert identity is not None
    assert identity.isbn == "9781590171998"
    assert identity.title == "Stoner"
    assert identity.work_id == "OL3511459W"
    assert identity.publisher == "New York Review Books"
    assert identity.published == "2006"
    assert identity.physical_format == "Trade Paperback"


def test_an_edition_with_no_format_is_still_an_identity():
    """Open Library does not know the target *Crash* edition is a paperback.

    A missing format is ordinary, not an error. Decision 33 records that its
    format coverage is worse than eBay's, which is why eBay's aspects remain
    the fallback rather than the other way round.
    """
    client = build_client(responds_with(CRASH))

    identity = client.identify_isbn("9780374524128")

    assert identity is not None
    assert identity.physical_format is None
    assert identity.publisher == "Farrar, Straus and Giroux"


def test_an_unparseable_publish_date_is_kept_as_written():
    """ "April 1, 1994" is not a date, and neither is "xxxx"."""
    client = build_client(responds_with(CRASH))

    identity = client.identify_isbn("9780374524128")

    assert identity is not None
    assert identity.published == "April 1, 1994"


def test_the_omnibus_comes_back_under_its_own_title():
    """The one thing this lookup exists to catch."""
    client = build_client(responds_with(OMNIBUS))

    identity = client.identify_isbn("9781598537024")

    assert identity is not None
    assert identity.title == "John Williams : Collected Novels"


def test_a_number_open_library_does_not_hold_is_an_answer_not_a_failure():
    """The five misses in S6's sample were non-English editions of the right book.

    Decision 33: a number Open Library cannot resolve must not exclude a
    listing, so this has to be a value a caller can act on.
    """
    client = build_client(responds_with({"error": "notfound"}, status_code=404))

    assert client.identify_isbn("9788925538297") is None


def test_being_unable_to_ask_is_not_the_same_as_an_answer():
    """An outage must not look like "Open Library does not have it".

    If these were the same value, every listing would quietly downgrade while
    Open Library was down, and nothing on screen would say so.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    client = build_client(handler)

    with pytest.raises(OpenLibraryUnavailable):
        client.identify_isbn("9781590171998")


def test_a_server_error_is_not_the_same_as_an_answer():
    client = build_client(responds_with({"error": "oops"}, status_code=503))

    with pytest.raises(OpenLibraryUnavailable):
        client.identify_isbn("9781590171998")


def test_a_record_with_no_title_is_unusable_rather_than_empty():
    """The title is the entire basis of the matching rule."""
    client = build_client(responds_with({"works": [{"key": "/works/OL1W"}]}))

    with pytest.raises(OpenLibraryUnavailable):
        client.identify_isbn("9781590171998")


def test_a_number_that_is_not_an_isbn_is_refused_before_anything_is_asked():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url)
        return httpx.Response(200, json=STONER)

    client = build_client(handler)

    with pytest.raises(ValueError):
        client.identify_isbn("not-a-number")
    assert asked == []


def test_an_isbn_10_is_asked_about_as_an_isbn_13():
    """One number, one notebook entry, however the seller typed it."""
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        return httpx.Response(200, json=STONER)

    identity = build_client(handler).identify_isbn("1590171993")

    assert asked == ["/isbn/9781590171998.json"]
    assert identity is not None and identity.isbn == "9781590171998"


# --- asking what a book is --------------------------------------------------


def test_a_title_search_returns_candidates_to_choose_from():
    client = build_client(responds_with(SEARCH))

    candidates = client.search_works("pride and prejudice", "jane austen")

    assert candidates[0] == Candidate(
        work_id="OL66554W",
        title="Pride and Prejudice",
        authors=("Jane Austen",),
        first_published=1813,
        edition_count=4042,
    )
    # The second is an omnibus, which is exactly why a person picks rather
    # than the app guessing.
    assert candidates[1].title.startswith("Novels")


def test_a_title_search_asks_for_named_fields_only():
    """A bare search returns tens of kilobytes per result; this returns under one."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=SEARCH)

    build_client(handler).search_works("stoner", "john williams")

    assert seen["q"] == "stoner john williams"
    assert "edition_count" in seen["fields"]


def test_an_edition_count_is_reported_and_never_fetched():
    """4,042 editions arrive as a number, not as 4,042 records."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json=SEARCH)

    candidates = build_client(handler).search_works("pride and prejudice")

    assert candidates[0].edition_count == 4042
    assert requests == ["/search.json"]


def test_a_search_with_nothing_to_search_for_is_refused():
    with pytest.raises(ValueError):
        build_client(responds_with(SEARCH)).search_works("   ")


# --- being a good guest -----------------------------------------------------


def test_every_request_says_who_is_calling():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json=STONER)

    build_client(handler).identify_isbn("9781590171998")

    assert seen["user-agent"] == USER_AGENT
    assert "github.com/loserpoints/book-watch" in seen["user-agent"]


def test_requests_are_spaced_out_without_the_caller_remembering_to():
    """The pause lives in the client because a loop that forgets it is the risk."""
    slept = []
    # The clock is read once after each request, and once before each request
    # that has one to wait for. Laid out in the order they happen:
    ticks = iter(
        [
            0.0,  # first request finishes
            0.2,  # second is about to start, 0.2s later
            1.5,  # second finishes
            2.3,  # third is about to start, 0.8s later
            3.0,  # third finishes
        ]
    )

    client = build_client(
        responds_with(STONER),
        min_interval_seconds=1.5,
        clock=lambda: next(ticks),
        sleep=slept.append,
    )

    client.identify_isbn("9781590171998")
    client.identify_isbn("9780374524128")
    client.identify_isbn("9781598537024")

    # The first waits for nothing. Each one after it waits out whatever is
    # left of the interval since the last.
    assert slept == [pytest.approx(1.3), pytest.approx(0.7)]


def test_a_failed_request_still_counts_as_having_bothered_them():
    """A timeout reached Open Library. Retrying it instantly is the thing to avoid."""
    slept = []
    ticks = iter([0.0, 0.5, 1.5])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    client = build_client(
        handler,
        min_interval_seconds=1.5,
        clock=lambda: next(ticks),
        sleep=slept.append,
    )

    with pytest.raises(OpenLibraryUnavailable):
        client.identify_isbn("9781590171998")
    with pytest.raises(OpenLibraryUnavailable):
        client.identify_isbn("9780374524128")

    assert slept == [pytest.approx(1.0)]


# --- the notebook -----------------------------------------------------------


@pytest.fixture
def database(tmp_path):
    connection = db.connect(tmp_path / "book-watch.db")
    db.migrate(connection)
    yield connection
    connection.close()


class CountingClient:
    """Stands in for the real client and counts how often it is bothered."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def identify_isbn(self, isbn):
        self.asked.append(isbn)
        answer = self.answers[isbn]
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_a_number_is_asked_about_once_and_then_never_again(database):
    client = build_client(responds_with(STONER))
    known = client.identify_isbn("9781590171998")
    counting = CountingClient({"9781590171998": known})
    resolver = Resolver(database, counting)

    first = resolver.identify("9781590171998")
    second = resolver.identify("1590171993")  # the same number, typed as ISBN-10

    assert first == second
    assert counting.asked == ["9781590171998"]


def test_a_miss_is_written_down_too(database):
    """Otherwise every poll re-asks for the same Korean edition forever."""
    counting = CountingClient({"9788925538297": None})
    resolver = Resolver(database, counting)

    assert resolver.identify("9788925538297") is None
    assert resolver.identify("9788925538297") is None
    assert counting.asked == ["9788925538297"]


def test_a_miss_is_asked_again_eventually(database):
    """Open Library gains records. Slowly, so this is a quarter, not a day."""
    counting = CountingClient({"9788925538297": None})
    day = datetime(2026, 1, 1, tzinfo=UTC)
    resolver = Resolver(database, counting, now=lambda: day)

    resolver.identify("9788925538297")

    later = Resolver(database, counting, now=lambda: day + timedelta(days=400))
    later.identify("9788925538297")

    assert counting.asked == ["9788925538297", "9788925538297"]


def test_what_a_number_is_never_expires(database):
    """9781590171998 will not stop being *Stoner*."""
    client = build_client(responds_with(STONER))
    known = client.identify_isbn("9781590171998")
    counting = CountingClient({"9781590171998": known})
    day = datetime(2026, 1, 1, tzinfo=UTC)

    Resolver(database, counting, now=lambda: day).identify("9781590171998")
    Resolver(database, counting, now=lambda: day + timedelta(days=4000)).identify(
        "9781590171998"
    )

    assert counting.asked == ["9781590171998"]


def test_a_failure_to_ask_is_not_written_down_as_a_miss(database):
    """The whole point of keeping the two apart.

    An outage must not poison the notebook with misses that never expire.
    """
    counting = CountingClient(
        {"9781590171998": OpenLibraryUnavailable("open library is down")}
    )
    resolver = Resolver(database, counting)

    with pytest.raises(OpenLibraryUnavailable):
        resolver.identify("9781590171998")

    rows = database.execute("SELECT count(*) AS n FROM openlibrary_edition").fetchone()
    assert rows["n"] == 0


def test_the_notebook_survives_a_restart(database, tmp_path):
    counting = CountingClient({"9788925538297": None})
    Resolver(database, counting).identify("9788925538297")
    database.commit()

    reopened = db.connect(tmp_path / "book-watch.db")
    try:
        Resolver(reopened, counting).identify("9788925538297")
    finally:
        reopened.close()

    assert counting.asked == ["9788925538297"]


def test_knowing_whether_a_number_needs_asking_about(database):
    """So the enrichment worker can say what a new book will cost before spending it."""
    counting = CountingClient({"9788925538297": None})
    resolver = Resolver(database, counting)

    assert not resolver.known("9788925538297")
    resolver.identify("9788925538297")
    assert resolver.known("9788925538297")
    assert not resolver.known("not-a-number")


# --- one real request -------------------------------------------------------


@pytest.mark.network
def test_a_real_lookup_returns_an_identity():
    """One real request. Run with `uv run pytest -m network`.

    Deselected by default. This is the test that catches Open Library changing
    its response shape, which the recorded ones structurally cannot.
    """
    with OpenLibraryClient() as client:
        identity = client.identify_isbn("9781590171998")

    assert identity is not None
    assert "stoner" in identity.title.lower()

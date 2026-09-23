"""Ask Open Library what a book is, or what a number is.

Two questions and nothing else:

    search_works("stoner", "john williams")  -> candidates to choose from
    identify_isbn("9781590171998")           -> what that number is

Open Library is a non-profit that states its API is not intended as a backend
for third-party services (decision 7). Everything here is shaped by that.

The pause between requests is enforced here rather than left to callers,
because "remember to sleep in the loop" fails the first time somebody writes a
loop. It is kept at **module** level rather than on the instance, because the
limit Open Library enforces is one request per second per *IP* — it does not
care how many client objects this process has made. Instance state cannot
enforce an address-level rule, and the difference is not theoretical: a
per-request client in the web layer once meant the pacing silently never
happened at all.

Run it directly to see what comes back:

    uv run python -m book_watch.openlibrary --title "stoner" --author "john williams"
    uv run python -m book_watch.openlibrary --isbn 9781590171998
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from book_watch.isbn import normalise
from book_watch.openlibrary.budget import CallBudget
from book_watch.openlibrary.errors import OpenLibraryUnavailable
from book_watch.openlibrary.models import Candidate, EditionIdentity

BASE_URL = "https://openlibrary.org"

DEFAULT_TIMEOUT_SECONDS = 30.0

#: Seconds to leave between requests.
#:
#: Open Library allows one request per second from an unidentified caller and
#: three from one that names a contact address. This is 0.67 a second: about a
#: third under the lower of those, which is what CLAUDE.md means by staying
#: well inside a published limit rather than close to it.
DEFAULT_MIN_INTERVAL_SECONDS = 1.5

#: When this process last spoke to Open Library, and the lock that keeps two
#: threads from deciding they may both go now.
#:
#: Module level on purpose. See the note at the top of this file: the limit is
#: per address, so this has to be per process.
_pace = threading.Lock()
_last_request_at: float | None = None


def forget_the_pace() -> None:
    """Clear the shared timestamp. For tests, which must not inherit each other's."""
    global _last_request_at
    with _pace:
        _last_request_at = None


#: How many candidates a title search offers. Enough to tell a book from its
#: omnibus and its sequels, few enough to read at a glance.
DEFAULT_CANDIDATE_LIMIT = 5

#: Services are entitled to know who is calling them. See CLAUDE.md.
USER_AGENT = (
    "book-watch/0.1 (personal book want-list tool; "
    "+https://github.com/loserpoints/book-watch)"
)

_Clock = Callable[[], float]
_Sleep = Callable[[float], None]


class OpenLibraryClient:
    """Talks to Open Library, slowly, on purpose, and countably.

    Safe to make several of. The pacing they share lives in this module rather
    than in any one of them, so two clients in two threads cannot between them
    go twice as fast — which is the only behaviour that matters, since the
    limit is per address.
    """

    def __init__(
        self,
        budget: CallBudget,
        *,
        client: httpx.Client | None = None,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        clock: _Clock = time.monotonic,
        sleep: _Sleep = time.sleep,
    ) -> None:
        # Required, with no default. A default here would be a way to opt out
        # of being counted without noticing, which is how the test suite
        # quietly started calling Open Library for real (decision 36).
        self._budget = budget
        self._min_interval = min_interval_seconds
        # Monotonic rather than wall-clock: this measures a gap between two
        # requests, and a system clock adjustment should not be able to grant
        # a burst of them.
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None
        if client is None:
            client = httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)
            self._owns_client = True
        else:
            self._owns_client = False
        self._client = client

    def search_works(
        self,
        title: str,
        author: str | None = None,
        *,
        limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> list[Candidate]:
        """Candidate books for a title, in the order Open Library ranks them.

        Asks for named fields rather than whole records. A bare search returns
        tens of kilobytes of catalogue metadata per result; the five fields a
        person needs to pick the right book fit in under a kilobyte for the
        whole list.
        """
        query = f"{title} {author}".strip() if author else title.strip()
        if not query:
            raise ValueError("a title search needs something to search for")
        payload = self._get(
            "/search.json",
            params={
                "q": query,
                "limit": limit,
                "fields": "key,title,author_name,first_publish_year,edition_count",
            },
        )
        docs = payload.get("docs")
        if not isinstance(docs, list):
            raise OpenLibraryUnavailable(
                f"search for {query!r} returned no docs list; got {type(docs).__name__}"
            )
        return [_candidate(doc) for doc in docs if isinstance(doc, dict)]

    def identify_isbn(self, isbn: str) -> EditionIdentity | None:
        """What this number is, or `None` if Open Library has no record of it.

        `None` is an answer, not a failure: Open Library told us it holds
        nothing for this number. Failing to ask raises `OpenLibraryUnavailable`
        instead. Decision 33 sends those two down different paths — an
        unheld number must not exclude a listing — so they must not be
        catchable by the same `except`.
        """
        normalised = normalise(isbn)
        if normalised is None:
            raise ValueError(
                f"{isbn!r} is not a valid ISBN. Normalise before asking, and "
                "skip the ones that come back None rather than asking anyway."
            )
        payload = self._get(f"/isbn/{normalised}.json", allow_missing=True)
        if payload is None:
            return None
        return _identity(normalised, payload)

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        allow_missing: bool = False,
    ) -> Any:
        """One request, once the pause has elapsed and the ceiling allows it."""
        self._wait_turn()
        # Counted *after* the pause, so the recorded time is within
        # milliseconds of the request itself. Counting before would make the
        # ledger read as though requests went out faster than they did, which
        # is exactly the question somebody reads it to answer.
        #
        # The cost is that a refusal arrives a second and a half late. Nothing
        # is sent either way, and a loop being refused slowly is a loop doing
        # less harm.
        self._budget.spend(path)
        try:
            response = self._client.get(
                f"{BASE_URL}{path}",
                params=params,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise OpenLibraryUnavailable(f"GET {path} failed: {exc}") from exc

        if allow_missing and response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise OpenLibraryUnavailable(
                f"GET {path} returned {response.status_code}: {response.text[:200]!r}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise OpenLibraryUnavailable(
                f"GET {path} returned {response.status_code} with a body that "
                f"is not JSON: {response.text[:200]!r}"
            ) from exc

    def _wait_turn(self) -> None:
        """Block until this process is allowed to speak to them again.

        The timestamp is stamped before the request rather than after, so the
        gap measured is between one request starting and the next — which is
        what "one request per second" means. Stamping afterwards would also
        count however long they took to answer, and a slow reply is not a
        reason to have been more polite than asked.

        It is stamped whether or not the request then succeeds. A request that
        timed out still reached them, and retrying it immediately is exactly
        what this exists to prevent.
        """
        global _last_request_at
        with _pace:
            if _last_request_at is not None:
                remaining = self._min_interval - (self._clock() - _last_request_at)
                if remaining > 0:
                    self._sleep(remaining)
            _last_request_at = self._clock()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenLibraryClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _candidate(doc: dict[str, Any]) -> Candidate:
    authors = doc.get("author_name")
    return Candidate(
        work_id=_work_id(doc.get("key")) or "",
        title=str(doc.get("title") or ""),
        authors=tuple(str(a) for a in authors) if isinstance(authors, list) else (),
        first_published=_optional_int(doc.get("first_publish_year")),
        edition_count=_optional_int(doc.get("edition_count")),
    )


def _identity(isbn: str, payload: dict[str, Any]) -> EditionIdentity:
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise OpenLibraryUnavailable(
            f"the record for {isbn} has no usable title; got {title!r}"
        )
    works = payload.get("works")
    work_key = works[0].get("key") if isinstance(works, list) and works else None
    return EditionIdentity(
        isbn=isbn,
        title=title.strip(),
        work_id=_work_id(work_key),
        publisher=_first_string(payload.get("publishers")),
        published=_optional_string(payload.get("publish_date")),
        physical_format=_optional_string(payload.get("physical_format")),
    )


def _work_id(key: Any) -> str | None:
    """`/works/OL3511459W` -> `OL3511459W`.

    Stored as a reference for looking something up by hand, never as identity.
    Decision 33: *Crash* is filed under five separate work ids and a title
    search returns two different *Pride and Prejudice* works, so anything that
    joined on this would be quietly wrong.
    """
    if not isinstance(key, str) or not key.strip():
        return None
    return key.strip().rsplit("/", 1)[-1] or None


def _first_string(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return _optional_string(value[0])
    return None


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

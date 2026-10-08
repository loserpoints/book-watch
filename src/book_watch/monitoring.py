"""What the app did, written as one line per event in one vocabulary.

The vocabulary and the line format are in `docs/rules/monitoring.md`. Every
outside call goes through `call`, every marketplace check of a book through
`check`, every job the app runs on its own through `job`, every request to the
app through `page`, and everything a person does through `action`. Nothing
else writes these lines, so the words stay the same everywhere.

What started the work, and which book it is about, are set once where the work
starts (`started_by`, `about`) and read by every line written beneath it. They
are context variables, so they follow the work into the thread or background
task it runs on, as long as that task is handed over with `carried`.
"""

from __future__ import annotations

import contextvars
import logging
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from book_watch import counts

logger = logging.getLogger("book_watch")

#: What started the work: daily, check, open, recheck, add, cover or test.
_trigger: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trigger", default="unknown"
)
#: The want-list book the work is about, as its id and title.
_book: contextvars.ContextVar[tuple[int, str | None] | None] = contextvars.ContextVar(
    "book", default=None
)
#: The call in progress, so code beneath it can say what the service answered.
_call: contextvars.ContextVar[Outcome | None] = contextvars.ContextVar(
    "call", default=None
)
#: The marketplace check in progress, so storing its copies can count them.
_check: contextvars.ContextVar[Outcome | None] = contextvars.ContextVar(
    "check", default=None
)


@dataclass
class Outcome:
    """What a call or check found, filled in by the code that makes it.

    Left alone, a call that returns is `ok` and one that raises is `failed`,
    with a reason read from the exception.
    """

    outcome: str | None = None
    reason: str | None = None
    status: int | None = None
    detail: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def failed(self, exc: BaseException) -> None:
        """Mark this failed because of `exc`, which the code caught."""
        self.reason = reason_for(exc, self.status, otherwise=None)
        self.outcome = "skipped" if self.reason in ("limit", "blocked") else "failed"
        self.detail = scrubbed(str(exc))


# Where work starts.


@contextmanager
def started_by(trigger: str) -> Iterator[None]:
    """Name what started the work done inside this block."""
    token = _trigger.set(trigger)
    try:
        yield
    finally:
        _trigger.reset(token)


@contextmanager
def about(book_id: int, title: str | None) -> Iterator[None]:
    """Name the want-list book the work inside this block is about."""
    token = _book.set((book_id, title))
    try:
        yield
    finally:
        _book.reset(token)


def handling(
    trigger: str, book_id: int | None = None, title: str | None = None
) -> None:
    """Name what started a request's work, and the book, for the rest of it.

    For request handlers only, which need no block: FastAPI runs each sync
    handler in its own copy of the context, so what is set here ends with the
    request and never reaches another.
    """
    _trigger.set(trigger)
    if book_id is not None:
        _book.set((book_id, title))


def trigger() -> str:
    return _trigger.get()


def carried[T](work: Callable[[], T]) -> Callable[[], T]:
    """`work`, run later with the trigger and book in force now.

    A FastAPI background task starts from the request's context, not from the
    handler's, so what the handler set would otherwise be lost.
    """
    context = contextvars.copy_context()
    return lambda: context.run(work)


# Lines.


def call_answered(status: int) -> None:
    """Record the status the service answered the call in progress with."""
    current = _call.get()
    if current is not None:
        current.status = status


def check_saw(copies: int, new: int, full: bool) -> None:
    """Record what the marketplace check in progress returned.

    The first record wins: AbeBooks' one page is stored twice, for everywhere
    and then for US sellers, and the first is the whole page.
    """
    current = _check.get()
    if current is not None and "copies" not in current.fields:
        current.fields.update(copies=copies, new=new, full=full)


@contextmanager
def call(service: str, endpoint: str) -> Iterator[Outcome]:
    """One request to an outside service, written as one line however it
    ends."""
    found = Outcome()
    token = _call.set(found)
    started = time.monotonic()
    try:
        yield found
    except BaseException as exc:
        _end_call(service, endpoint, found, started, exc)
        raise
    else:
        _end_call(service, endpoint, found, started, None)
    finally:
        _call.reset(token)


def _end_call(
    service: str,
    endpoint: str,
    found: Outcome,
    started: float,
    exc: BaseException | None,
) -> None:
    outcome, reason = _settle(found, exc, "unreadable")
    if exc is not None:
        # So a check or job this failure ends carries the same reason.
        exc.monitoring_reason = reason  # type: ignore[attr-defined]
    seconds = time.monotonic() - started
    counts.calls.labels(service, endpoint, _trigger.get(), outcome, reason or "").inc()
    counts.call_seconds.labels(service, endpoint).observe(seconds)
    _write(
        logging.WARNING if outcome in ("failed", "skipped") else logging.INFO,
        "call",
        service=service,
        endpoint=endpoint,
        **_context(),
        outcome=outcome,
        reason=reason,
        status=found.status,
        **found.fields,
        ms=_since(started),
        detail=found.detail or (scrubbed(str(exc)) if exc is not None else None),
    )


@contextmanager
def check(marketplace: str) -> Iterator[Outcome]:
    """One marketplace check of one book, written as one line however it
    ends."""
    found = Outcome()
    token = _check.set(found)
    started = time.monotonic()
    error: BaseException | None = None
    try:
        yield found
    except BaseException as exc:
        error = exc
        raise
    finally:
        _check.reset(token)
        outcome, reason = _settle(found, error, None)
        if outcome == "ok" and found.fields.get("copies") == 0:
            outcome = "empty"
        counts.checks.labels(marketplace, _trigger.get(), outcome).inc()
        counts.check_copies.labels(marketplace).inc(found.fields.get("copies", 0))
        counts.check_new_copies.labels(marketplace).inc(found.fields.get("new", 0))
        if found.fields.get("full"):
            counts.checks_full.labels(marketplace).inc()
        _write(
            logging.WARNING if outcome in ("failed", "skipped") else logging.INFO,
            "check",
            marketplace=marketplace,
            **_context(),
            outcome=outcome,
            reason=reason,
            **found.fields,
            ms=_since(started),
            detail=found.detail
            or (scrubbed(str(error)) if error is not None else None),
        )


@contextmanager
def job(name: str) -> Iterator[Outcome]:
    """One run of a job the app does on its own, written as a start line and
    an end line. A job that raises ends `failed`, at error level, with its
    traceback."""
    found = Outcome()
    started = time.monotonic()
    _write(logging.INFO, "job", name=name, phase="start", **_context())
    try:
        yield found
    except Exception as exc:
        exc.monitoring_logged = True  # type: ignore[attr-defined]
        _count_job(name, "failed", started)
        _write(
            logging.ERROR,
            "job",
            name=name,
            phase="end",
            **_context(),
            outcome="failed",
            **found.fields,
            ms=_since(started),
            detail=scrubbed(str(exc)),
            exc_info=exc,
        )
        raise
    outcome = found.outcome or "ok"
    _count_job(name, outcome, started)
    _write(
        logging.INFO if outcome == "ok" else logging.WARNING,
        "job",
        name=name,
        phase="end",
        **_context(),
        outcome=outcome,
        reason=found.reason,
        **found.fields,
        ms=_since(started),
        detail=found.detail,
    )


def _count_job(name: str, outcome: str, started: float) -> None:
    counts.jobs.labels(name, outcome).inc()
    counts.job_seconds.labels(name).observe(time.monotonic() - started)


def page(path: str, status: int, ms: int, route: str = "other") -> None:
    """One request to the app. A request that crashed is answered 500, and
    uvicorn writes its traceback on the line after. Another 5xx is the app
    saying a service it needs is down, which it carried on from."""
    level = (
        logging.ERROR
        if status == 500
        else logging.WARNING
        if status > 500
        else logging.INFO
    )
    counts.pages.labels(route, str(status)).inc()
    counts.page_seconds.labels(route).observe(ms / 1000)
    _write(
        level,
        "page",
        path=path,
        status=status,
        ms=ms,
    )


def action(name: str, **fields: Any) -> None:
    """Something a person did in the app. It is its own trigger, so it names
    none."""
    counts.actions.labels(name).inc()
    _write(logging.INFO, "action", name=name, **fields)


# The reason a call or check failed.


def _settle(
    found: Outcome, exc: BaseException | None, otherwise: str | None
) -> tuple[str, str | None]:
    if exc is None:
        return found.outcome or "ok", found.reason
    reason = found.reason or reason_for(exc, found.status, otherwise=otherwise)
    if found.outcome is not None:
        return found.outcome, reason
    return ("skipped" if reason in ("limit", "blocked") else "failed"), reason


def reason_for(
    exc: BaseException,
    status: int | None = None,
    *,
    otherwise: str | None = "unreadable",
) -> str | None:
    """The vocabulary's word for why a call failed.

    A check or a job takes the reason of the call that failed beneath it.
    Within a call, a failure that is no timeout, no refusal and no outage is
    an answer the app couldn't read, which is `otherwise`'s default.
    """
    # Imported here so this module loads before the clients that use it.
    import httpx

    from book_watch.config import MissingCredentialError
    from book_watch.openlibrary.budget import BudgetExhausted
    from book_watch.pages import RefusedPath

    chain = _chain(exc)
    for link in chain:
        known = getattr(link, "monitoring_reason", None)
        if known is not None:
            return known
    if any(isinstance(link, RefusedPath) for link in chain):
        return "blocked"
    if any(isinstance(link, BudgetExhausted) for link in chain):
        return "limit"
    if any(isinstance(link, MissingCredentialError) for link in chain):
        return "setup"
    if any(isinstance(link, httpx.TimeoutException) for link in chain):
        return "timeout"
    if status is not None and status >= 500:
        return "down"
    if status is not None and status >= 400:
        return "refused"
    if any(isinstance(link, httpx.HTTPError) for link in chain):
        return "down"
    return otherwise


def logged(exc: BaseException) -> bool:
    """Whether a job's end line has already written this, traceback and all."""
    return getattr(exc, "monitoring_logged", False)


def _chain(exc: BaseException) -> list[BaseException]:
    links: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in links:
        links.append(current)
        current = current.__cause__ or current.__context__
    return links


# Writing a line.


def _context() -> dict[str, Any]:
    book = _book.get()
    return {
        "trigger": _trigger.get(),
        "book": book[0] if book else None,
        "title": book[1] if book else None,
    }


def _since(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _write(
    level: int,
    event: str,
    *,
    exc_info: BaseException | None = None,
    **fields: Any,
) -> None:
    logger.log(
        level,
        line(event, **fields),
        exc_info=exc_info,
        extra={"logfmt": True},
    )


def line(event: str, **fields: Any) -> str:
    """`event=… key=value …`, in the order given, leaving out empty fields."""
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_value(value)}")
    return " ".join(parts)


_BARE = re.compile(r"^[^\s\"=\\]+$")


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value)
    if _BARE.match(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def scrubbed(text: str, limit: int = 300) -> str:
    """The message with any email address, bearer token or Resend key taken
    out, cut short. A service's error can quote the recipient back."""
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "<address>", text)
    text = re.sub(r"\bre_\w+", "<key>", text)
    # An eBay token holds ^ and #, so everything up to a space or a quote.
    text = re.sub(r"(?i)\b(bearer|basic)\s+[^\s'\",;)]+", r"\1 <token>", text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Logfmt(logging.Formatter):
    """Every line as `level=… event=…`, whoever wrote it.

    Lines from this module are already in the format. Anything else, such as
    uvicorn's start-up or a library's warning, becomes `event=log` with its
    logger and message, so the whole log reads one way.
    """

    _LEVELS = {"WARNING": "warn", "CRITICAL": "error"}

    def format(self, record: logging.LogRecord) -> str:
        level = self._LEVELS.get(record.levelname, record.levelname.lower())
        if getattr(record, "logfmt", False):
            body = record.getMessage()
        else:
            body = line("log", logger=record.name, msg=record.getMessage())
        text = f"level={level} {body}"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


def configure() -> None:
    """Send every line through `Logfmt`, and quiet the lines it replaces.

    Uvicorn sets up its own loggers before it imports the app, so this runs at
    import and takes them over: its per-request line is replaced by `page`,
    and its other lines join the root handler.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(Logfmt())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn = logging.getLogger(name)
        uvicorn.handlers = []
        uvicorn.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True
    # httpx writes a line per request at INFO. `call` says more.
    logging.getLogger("httpx").setLevel(logging.WARNING)

"""The morning email (S40, #143).

After the daily check, one email lists every copy worth interrupting me for,
and on mornings with none, nothing is sent. A copy is worth it when its book
has a limit, it is certainly this book, its delivered price is at or under
the limit, it is new since I last opened the book, and it has never been in
an email before. That last rule is what keeps the email from repeating
itself: a copy is in at most one, ever.

Sent through Resend from its shared address, which needs no domain of our own
and delivers only to the Resend account's own address, the one recipient.
"""

from __future__ import annotations

import html
import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, replace
from decimal import Decimal

import httpx

from book_watch import copies, wantlist
from book_watch.config import AlertConfig, MissingCredentialError, load_alert_config
from book_watch.copies import Copy
from book_watch.ebay.auth import USER_AGENT
from book_watch.ebay.search import Money
from book_watch.wantlist import Entry
from book_watch.web.book_view import money

logger = logging.getLogger(__name__)

ConnectFn = Callable[[], sqlite3.Connection]
PostFn = Callable[..., httpx.Response]

RESEND_URL = "https://api.resend.com/emails"
#: Resend's shared sending address. It delivers only to the account's own
#: address, which is why no domain is needed.
SENDER = "book-watch <onboarding@resend.dev>"
APP_URL = "https://book-watch.fly.dev"
TIMEOUT_SECONDS = 30


class AlertError(Exception):
    """The email could not be sent."""


@dataclass(frozen=True, slots=True)
class Alert:
    """One copy for the email, and the book it is a copy of."""

    entry: Entry
    copy: Copy
    #: What it cost at my last visit, when it is here because it dropped
    #: under the limit since then (S41). None for a new copy.
    was: Money | None = None


def due(connection: sqlite3.Connection) -> list[Alert]:
    """Every copy that belongs in this morning's email: under its book's
    limit, never emailed, and either new since I last opened the book or
    over the limit when I did."""
    found = []
    for entry in wantlist.all_books(connection):
        ceiling = entry.will_pay
        if ceiling is None:
            continue
        for copy in copies.for_entry(connection, entry, scope="us"):
            if (
                copy.tier != "certain"
                or copy.against(ceiling) != "under"
                or _emailed(connection, copy.item_id, entry.work_id)
            ):
                continue
            if copies.is_new(copy, entry.last_looked):
                found.append(Alert(entry, copy))
                continue
            then = _at_last_visit(connection, entry, copy)
            if then is not None and then.against(ceiling) == "over":
                found.append(Alert(entry, copy, was=then.landed_cost or then.price))
    return found


def _at_last_visit(
    connection: sqlite3.Connection, entry: Entry, copy: Copy
) -> Copy | None:
    """This copy as it was priced when I last opened the book, or None if it
    had not been seen by then.

    Read from the price history: its last sighting at or before that visit.
    """
    if entry.looked_at is None:
        return None
    row = connection.execute(
        "SELECT sighting.price, sighting.currency, sighting.shipping "
        "FROM sighting JOIN sweep ON sweep.id = sighting.sweep_id "
        "WHERE sighting.work_id = ? AND sighting.item_id = ? AND sweep.at <= ? "
        "ORDER BY sighting.sweep_id DESC LIMIT 1",
        (entry.work_id, copy.item_id, entry.looked_at),
    ).fetchone()
    if row is None:
        return None
    currency = row["currency"]
    return replace(
        copy,
        price=Money(Decimal(row["price"]), currency),
        shipping=Money(Decimal(row["shipping"]), currency)
        if row["shipping"] is not None
        else None,
    )


def _emailed(connection: sqlite3.Connection, item_id: str, work_id: int) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM emailed_copy WHERE item_id = ? AND work_id = ?",
            (item_id, work_id),
        ).fetchone()
        is not None
    )


def compose(alerts: list[Alert]) -> tuple[str, str, str]:
    """The subject, the HTML body and the plain-text body."""
    count = len(alerts)
    subject = f"{count} cop{'y' if count == 1 else 'ies'} under your limit"
    parts_html, parts_text = [], []
    for alert in alerts:
        entry, copy = alert.entry, alert.copy
        delivered = copy.landed_cost
        limit = entry.will_pay
        assert delivered is not None and limit is not None  # `due` checked both.
        price = f"{money(delivered)} delivered, limit {money(limit)}"
        if alert.was is not None:
            price = f"Price drop from {money(alert.was)}: {price}"
        condition = copy.condition or "condition unstated"
        book_url = f"{APP_URL}/book/{entry.id}"
        parts_html.append(
            f"<p><b>{html.escape(entry.name)}</b><br>"
            f"{html.escape(price)} · {html.escape(condition)}<br>"
            f'<a href="{html.escape(copy.url)}">{html.escape(copy.title)}</a><br>'
            f'<a href="{book_url}">Open in book-watch</a></p>'
        )
        parts_text.append(
            f"{entry.name}\n{price} · {condition}\n{copy.title}\n{copy.url}\n"
            f"Open in book-watch: {book_url}\n"
        )
    return subject, "\n".join(parts_html), "\n".join(parts_text)


def send(
    config: AlertConfig, subject: str, body_html: str, body_text: str, post: PostFn
) -> None:
    """One request to Resend. Raises `AlertError` if it did not take it."""
    try:
        response = post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "User-Agent": USER_AGENT,
            },
            json={
                "from": SENDER,
                "to": [config.to],
                "subject": subject,
                "html": body_html,
                "text": body_text,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise AlertError(f"Resend could not be reached: {exc}") from exc
    if response.status_code >= 300:
        # Resend's error names the problem and never echoes the key.
        raise AlertError(f"Resend said {response.status_code}: {response.text}")


def notify(
    connect: ConnectFn,
    *,
    config: Callable[[], AlertConfig] = load_alert_config,
    post: PostFn = httpx.post,
) -> int:
    """Send this morning's email if anything is due. Returns how many copies
    it listed. Raises `AlertError` when sending failed, having recorded
    nothing, so the next morning tries the same copies again."""
    try:
        settings = config()
    except MissingCredentialError as exc:
        logger.info("Email is off: %s", exc)
        return 0
    with closing(connect()) as connection:
        alerts = due(connection)
        if not alerts:
            return 0
        send(settings, *compose(alerts), post)
        connection.executemany(
            "INSERT OR IGNORE INTO emailed_copy (item_id, work_id) VALUES (?, ?)",
            [(alert.copy.item_id, alert.entry.work_id) for alert in alerts],
        )
        connection.commit()
    return len(alerts)

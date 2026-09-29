"""The morning email (S40, #143): what goes in it, and that it goes once."""

from contextlib import closing
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from book_watch import alerts, daily, db, wantlist
from book_watch.config import AlertConfig, MissingCredentialError

CRASH = "9780099448396"
STONER = "9781590171998"
SETTINGS = AlertConfig(api_key="re_test_key", to="reader@example.com")


@pytest.fixture
def connect(tmp_path):
    path = tmp_path / "book-watch.db"

    def connect():
        connection = db.connect(path)
        db.migrate(connection)
        return connection

    with closing(connect()) as connection:
        wantlist.add(connection, CRASH, "Crash")
        wantlist.add(connection, STONER, "Stoner")
        # Crash has a $10 limit and was last opened two days ago. Stoner has
        # no limit.
        connection.execute(
            "UPDATE entry SET ceiling = '10.00', ceiling_currency = 'USD', "
            "looked_at = datetime('now', '-2 days') WHERE typed = ?",
            (CRASH,),
        )
        connection.execute(
            "UPDATE entry SET looked_at = datetime('now', '-2 days') WHERE typed = ?",
            (STONER,),
        )
        connection.commit()
    return connect


def a_copy(connect, isbn, item, price, shipping, first_seen, listed):
    """A copy certainly this book, in the book's newest US sweep."""
    with closing(connect()) as connection:
        work_id = connection.execute(
            "SELECT work_id FROM entry WHERE typed = ?", (isbn,)
        ).fetchone()["work_id"]
        sweep = connection.execute(
            "SELECT id FROM sweep WHERE work_id = ? AND scope = 'us'", (work_id,)
        ).fetchone()
        if sweep is None:
            sweep_id = connection.execute(
                "INSERT INTO sweep (work_id, scope, asked_for) VALUES (?, 'us', 50)",
                (work_id,),
            ).lastrowid
        else:
            sweep_id = sweep["id"]
        connection.execute(
            "INSERT INTO copy (item_id, work_id, title, url, price, currency, "
            "shipping, condition, first_seen_at, listed_at) "
            "VALUES (?, ?, ?, ?, ?, 'USD', ?, 'Good', "
            "datetime('now', ?), datetime('now', ?))",
            (
                item,
                work_id,
                f"Listing {item}",
                f"https://www.ebay.com/itm/{item}",
                price,
                shipping,
                first_seen,
                listed,
            ),
        )
        connection.execute(
            "INSERT INTO copy_seen (item_id, work_id, sweep_id, scope) "
            "VALUES (?, ?, ?, 'us')",
            (item, work_id, sweep_id),
        )
        connection.execute(
            "INSERT OR IGNORE INTO listing_declaration (item_id, isbn) VALUES (?, ?)",
            (item, isbn),
        )
        connection.execute(
            "INSERT OR IGNORE INTO openlibrary_edition (isbn, found, title) "
            "VALUES (?, 1, ?)",
            (isbn, "Crash" if isbn == CRASH else "Stoner"),
        )
        connection.commit()


@pytest.fixture
def morning(connect):
    """One copy that belongs in the email, and one of each that doesn't."""
    a_copy(connect, CRASH, "new-cheap", "8.00", "1.00", "-1 day", "-1 day")
    a_copy(connect, CRASH, "new-dear", "12.00", "0.00", "-1 day", "-1 day")
    a_copy(connect, CRASH, "no-postage", "8.00", None, "-1 day", "-1 day")
    a_copy(connect, CRASH, "seen", "8.00", "0.00", "-3 days", "-3 days")
    a_copy(connect, CRASH, "relisted", "8.00", "0.00", "-1 day", "-60 days")
    a_copy(connect, STONER, "no-limit", "3.00", "0.00", "-1 day", "-1 day")
    return connect


class Resend:
    """Stands in for Resend, and records every request."""

    def __init__(self, status=200):
        self.status = status
        self.sent = []

    def __call__(self, url, **kwargs):
        self.sent.append({"url": url, **kwargs})
        return httpx.Response(
            self.status,
            json={"id": "email-1"},
            request=httpx.Request("POST", url),
        )


def notify(connect, resend, settings=SETTINGS):
    return alerts.notify(connect, config=lambda: settings, post=resend)


# --- what belongs in the email ----------------------------------------------


def test_only_a_new_certain_copy_under_its_limit_belongs(morning):
    with closing(morning()) as connection:
        due = alerts.due(connection)

    assert [alert.copy.item_id for alert in due] == ["new-cheap"]


def test_the_email_names_the_book_the_price_and_both_links(morning):
    resend = Resend()

    assert notify(morning, resend) == 1

    [sent] = resend.sent
    body = sent["json"]
    assert sent["url"] == "https://api.resend.com/emails"
    assert sent["headers"]["Authorization"] == "Bearer re_test_key"
    assert body["to"] == ["reader@example.com"]
    assert body["from"] == "book-watch <onboarding@resend.dev>"
    assert body["subject"] == "1 copy under your limit"
    assert "Crash" in body["text"]
    assert "$9 delivered, limit $10" in body["text"]
    assert "https://www.ebay.com/itm/new-cheap" in body["text"]
    assert "https://book-watch.fly.dev/book/1" in body["text"]


def test_a_copy_is_never_in_two_emails(morning):
    resend = Resend()
    notify(morning, resend)

    assert notify(morning, resend) == 0
    assert len(resend.sent) == 1


def test_no_copy_worth_it_means_no_email(connect):
    a_copy(connect, CRASH, "seen", "8.00", "0.00", "-3 days", "-3 days")
    resend = Resend()

    assert notify(connect, resend) == 0
    assert resend.sent == []


def test_without_a_key_email_is_off_and_nothing_is_sent(morning):
    def missing():
        raise MissingCredentialError("RESEND_API_KEY is not set.")

    resend = Resend()

    assert alerts.notify(morning, config=missing, post=resend) == 0
    assert resend.sent == []


def test_a_failed_send_records_nothing_so_tomorrow_tries_again(morning):
    with pytest.raises(alerts.AlertError):
        notify(morning, Resend(status=500))

    retry = Resend()
    assert notify(morning, retry) == 1


def test_resend_out_of_reach_is_a_failed_send(morning):
    def unreachable(url, **kwargs):
        raise httpx.ConnectError("no route", request=httpx.Request("POST", url))

    with pytest.raises(alerts.AlertError):
        notify(morning, unreachable)


def test_the_key_never_shows_in_its_settings():
    assert "re_test_key" not in repr(SETTINGS)
    assert "reader@example.com" not in repr(SETTINGS)


# --- the daily check ----------------------------------------------------------


def no_search(query, limit, **kwargs):
    return []


def test_the_daily_check_records_how_many_it_emailed(connect):
    daily.run(connect, no_search, lambda w: None, lambda: 0, lambda: 3)

    with closing(connect()) as connection:
        run = connection.execute("SELECT * FROM daily_run").fetchone()
    assert run["outcome"] == "ok"
    assert run["emailed"] == 3


def test_a_failed_email_is_logged_and_not_shown_in_the_app(connect, caplog):
    """For the logs, not the app. The check itself went fine."""

    def broken():
        raise alerts.AlertError("Resend said 500")

    with caplog.at_level("WARNING", logger="book_watch.daily"):
        daily.run(connect, no_search, lambda w: None, lambda: 0, broken)

    with closing(connect()) as connection:
        run = connection.execute("SELECT * FROM daily_run").fetchone()
        said = daily.status(connection, datetime.now(UTC) + timedelta(minutes=1))
    assert run["outcome"] == "ok"
    assert run["email_failed"] == 1
    assert said is None
    assert "could not send its email: Resend said 500" in caplog.text

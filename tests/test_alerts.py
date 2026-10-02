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
    assert "https://book-watch-alan.fly.dev/book/1" in body["text"]


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


# --- price drops (S41, #165) --------------------------------------------------


def a_past_price(connect, isbn, item, price, shipping, when):
    """What this copy cost at a moment in the past, as the price history
    records it. Filed under a past 'everywhere' search, so the book's current
    US search is still the newest."""
    with closing(connect()) as connection:
        work_id = connection.execute(
            "SELECT work_id FROM entry WHERE typed = ?", (isbn,)
        ).fetchone()["work_id"]
        sweep_id = connection.execute(
            "INSERT INTO sweep (work_id, scope, asked_for, at) "
            "VALUES (?, 'everywhere', 50, datetime('now', ?))",
            (work_id, when),
        ).lastrowid
        connection.execute(
            "INSERT INTO sighting (item_id, work_id, sweep_id, price, currency, "
            "shipping) VALUES (?, ?, ?, ?, 'USD', ?)",
            (item, work_id, sweep_id, price, shipping),
        )
        connection.commit()


@pytest.fixture
def drops(connect):
    """Crash was last opened two days ago. Since then, one copy seen over the
    limit dropped under it, and one was under all along."""
    a_copy(connect, CRASH, "dropped", "8.00", "1.00", "-4 days", "-4 days")
    a_past_price(connect, CRASH, "dropped", "12.00", "1.00", "-3 days")
    a_past_price(connect, CRASH, "dropped", "8.00", "1.00", "-1 day")
    a_copy(connect, CRASH, "always-under", "8.00", "0.00", "-4 days", "-4 days")
    a_past_price(connect, CRASH, "always-under", "8.00", "0.00", "-3 days")
    return connect


def test_a_copy_that_dropped_under_the_limit_since_i_looked_belongs(drops):
    with closing(drops()) as connection:
        due = alerts.due(connection)

    assert [(a.copy.item_id, str(a.was.amount)) for a in due] == [("dropped", "13.00")]


def test_the_email_says_it_is_a_price_drop_and_from_what(drops):
    resend = Resend()

    notify(drops, resend)

    body = resend.sent[0]["json"]["text"]
    assert "Price drop from $13: $9 delivered, limit $10" in body


def test_a_dropped_copy_is_emailed_once(drops):
    resend = Resend()
    notify(drops, resend)

    assert notify(drops, resend) == 0
    assert len(resend.sent) == 1


def test_a_drop_i_have_already_seen_is_not_emailed(drops):
    """Opened again after the drop: I have seen the new price."""
    with closing(drops()) as connection:
        connection.execute("UPDATE entry SET looked_at = datetime('now')")
        connection.commit()
        assert alerts.due(connection) == []


def test_new_copies_and_drops_share_one_email(drops):
    a_copy(drops, CRASH, "new-cheap", "8.00", "1.00", "-1 day", "-1 day")
    resend = Resend()

    assert notify(drops, resend) == 2
    assert len(resend.sent) == 1
    assert resend.sent[0]["json"]["subject"] == "2 copies under your limit"


def test_raising_a_limit_never_sends_an_email(connect):
    """A copy over the old limit, under the new one, at an unchanged price.
    The old price is judged against the limit as it is now, so a raise can
    only remove drops, never make one."""
    a_copy(connect, CRASH, "unchanged", "12.00", "0.00", "-4 days", "-4 days")
    a_past_price(connect, CRASH, "unchanged", "12.00", "0.00", "-3 days")
    with closing(connect()) as connection:
        connection.execute(
            "UPDATE entry SET ceiling = '15.00' WHERE typed = ?", (CRASH,)
        )
        connection.commit()
        assert alerts.due(connection) == []


# --- the test email (S42, #172) ----------------------------------------------


def test_the_test_email_sends_one_fixed_message():
    resend = Resend()

    said = alerts.send_test(config=lambda: SETTINGS, post=resend)

    assert said == "Test email sent."
    [sent] = resend.sent
    assert sent["json"]["subject"] == "book-watch test email"
    assert sent["json"]["to"] == ["reader@example.com"]


def test_the_test_email_links_to_the_app():
    # So the address the morning email links to can be checked on demand.
    resend = Resend()

    alerts.send_test(config=lambda: SETTINGS, post=resend)

    [sent] = resend.sent
    assert "https://book-watch-alan.fly.dev" in sent["json"]["text"]
    assert 'href="https://book-watch-alan.fly.dev"' in sent["json"]["html"]


def test_the_test_email_leaves_the_morning_email_alone(morning):
    alerts.send_test(config=lambda: SETTINGS, post=Resend())

    resend = Resend()
    assert notify(morning, resend) == 1


def test_the_command_says_email_is_off_and_which_secret(capsys):
    def missing():
        raise MissingCredentialError("RESEND_API_KEY is not set.")

    status = alerts.main(["test"], run=lambda: alerts.send_test(config=missing))

    assert status == 1
    assert "Email is off: RESEND_API_KEY is not set." in capsys.readouterr().out


def test_the_command_gives_resends_reason_without_the_address_or_key(capsys):
    def rejected():
        raise alerts.AlertError(
            'Resend said 403: {"message": "You can only send testing emails to '
            "your own email address (reader@example.com). Key re_abc123 lacks "
            'access."}'
        )

    status = alerts.main(["test"], run=rejected)

    out = capsys.readouterr().out
    assert status == 1
    assert "Test email failed: Resend said 403" in out
    assert "reader@example.com" not in out
    assert "re_abc123" not in out


def test_the_command_prints_the_line_the_workflow_looks_for(capsys):
    status = alerts.main(["test"], run=lambda: "Test email sent.")

    assert status == 0
    assert capsys.readouterr().out.strip() == "Test email sent."

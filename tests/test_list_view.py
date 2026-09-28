"""The want-list's values for the system's book row (S34, #98).

The states S26 kept apart must stay apart: nobody has looked, nothing is
listed, copies but none comparable, only maybes, and a cheapest copy.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from book_watch.ebay.search import Money
from book_watch.standing import Glance, Headline, Market
from book_watch.wantlist import Entry
from book_watch.web import list_view
from book_watch.web.filters import since


def an_entry(**extra):
    fields = dict(
        id=1,
        work_id=1,
        hunt="reader",
        title="Crash",
        author="J. G. Ballard",
        added_at=(datetime.now(UTC) - timedelta(weeks=3)).strftime("%Y-%m-%d %H:%M:%S"),
        typed="9780099448396",
        edition_count=1,
        resolved_at="2026-09-01",
        enriched_at="2026-09-01",
        copies_fetched_at="2026-09-01",
    )
    fields.update(extra)
    return Entry(**{k: v for k, v in fields.items() if k in Entry.__dataclass_fields__})


def a_glance(**extra):
    fields = dict(checked=datetime.now(UTC), listed=0, uncertain=0, headline=None)
    fields.update(extra)
    return Glance(**fields)


def test_the_states_are_kept_apart():
    entry = an_entry()
    assert list_view.row(entry, None)["state"] == "unchecked"
    assert list_view.row(entry, a_glance(), "checking")["state"] == "checking"
    assert list_view.row(entry, a_glance(), "failed")["state"] == "failed"
    assert list_view.row(entry, a_glance())["state"] == "none"
    maybes = list_view.row(entry, a_glance(uncertain=2))
    assert (maybes["state"], maybes["maybes"]) == ("maybes", 2)
    # Copies, none comparable: a count, and no price to lead with.
    listed = list_view.row(entry, a_glance(listed=3))
    assert (listed["state"], listed["listed"]) == ("ok", 3)
    assert "price_text" not in listed


def test_added_is_how_long_ago():
    """#22: how long it has waited, not the day it went on."""
    assert list_view.row(an_entry(), None)["added"] == "3w"


def usd(amount):
    return Money(Decimal(amount), "USD")


def test_the_cheapest_leads_and_the_strip_draws_every_price_seen():
    market = Market("used", listed=3, seen=4, low=usd("10"), high=usd("27"))
    glance = a_glance(
        listed=3,
        headline=Headline(market=market, cheapest=usd("10.49"), verdict="under"),
        seen_prices={
            ("used", "USD"): [Decimal(x) for x in ("10.49", "12", "14", "27")]
        },
    )

    row = list_view.row(an_entry(), glance)

    assert (row["price_text"], row["verdict"], row["listed"]) == ("$10.49", "under", 3)
    assert "4 asking prices seen, $10 to $27" in row["strip"]


def test_years_once_a_year_has_passed():
    assert since(datetime.now(UTC) - timedelta(days=800)) == "2y"

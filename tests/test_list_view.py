"""The want-list's values for the system's book row (S34, #98).

The states S26 kept apart must stay apart: nobody has looked, nothing is
listed, copies but none comparable, only maybes, and a cheapest copy.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from book_watch.ebay.search import Money
from book_watch.purchases import Purchase
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
    # Being checked is working, not a state of its own (S68, #240): the row
    # keeps what it knew, and says "digging" in place of its counts.
    checking = list_view.row(entry, a_glance(), "checking")
    assert (checking["working"], checking["state"]) == (True, "none")
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
    market = Market(listed=3, seen=4, low=usd("10"), high=usd("27"))
    glance = a_glance(
        listed=3,
        headline=Headline(market=market, cheapest=usd("10.49"), verdict="under"),
        seen_prices={"USD": [Decimal(x) for x in ("10.49", "12", "14", "27")]},
    )

    row = list_view.row(an_entry(), glance)

    assert (row["price_text"], row["verdict"], row["listed"]) == ("$10.49", "under", 3)
    assert "4 asking prices seen, $10 to $27" in row["strip"]


def test_years_once_a_year_has_passed():
    assert since(datetime.now(UTC) - timedelta(days=800)) == "2y"


def test_a_digging_row_keeps_its_last_price_and_hides_its_counts():
    """S68 (#240): counts are not true until the copies are examined, so the
    row works in their place. The last price stays meanwhile."""
    market = Market(listed=3, seen=3, low=usd("10"), high=usd("12"))
    glance = a_glance(
        listed=3,
        headline=Headline(market=market, cheapest=usd("10"), verdict="no ceiling"),
    )

    row = list_view.row(an_entry(), glance, "checking")

    assert row["working"] is True
    assert row["price_text"] == "$10"


def test_listed_counts_every_copy_new_counts():
    """S68 (#240): "listed" counted only copies with a delivered price, and
    "new" every certain copy, so a row could read "17 listed · 18 new"."""
    market = Market(listed=17, seen=17, low=usd("10"), high=usd("30"))
    glance = a_glance(
        listed=18,
        new=18,
        headline=Headline(market=market, cheapest=usd("10"), verdict="no ceiling"),
    )

    row = list_view.row(an_entry(), glance)

    assert row["new"] <= row["listed"]
    assert row["listed"] == 18


def a_purchase(**extra):
    fields = dict(
        id=1,
        title="Stoner",
        author="John Williams",
        cover_id=None,
        paid=usd("7.80"),
        marketplace="ebay",
        shop=None,
        bought_on=date(2026, 10, 3),
        limit=usd("8"),
    )
    fields.update(extra)
    return Purchase(**fields)


def test_a_bought_row_says_where_and_the_day_without_the_year_this_year():
    today = date(2026, 10, 7)

    this_year = list_view.bought_row(a_purchase(), today)
    last_year = list_view.bought_row(
        a_purchase(bought_on=date(2025, 12, 28), marketplace=None, shop="Strand"),
        today,
    )

    assert this_year["where_when"] == "on eBay · Oct 3"
    assert last_year["where_when"] == "on Strand · Dec 28, 2025"


def test_a_bought_row_is_judged_against_the_limit_it_had():
    assert list_view.bought_row(a_purchase())["verdict"] == "under"
    assert list_view.bought_row(a_purchase(paid=usd("8")))["verdict"] == "under"
    assert list_view.bought_row(a_purchase(paid=usd("8.01")))["verdict"] == "over"
    no_limit = list_view.bought_row(a_purchase(limit=None))
    assert (no_limit["verdict"], no_limit["limit_text"]) == (None, "no limit set")


def test_the_bought_total_leaves_out_a_sum_across_currencies():
    gbp = Money(Decimal("5"), "GBP")

    assert list_view.bought_total([a_purchase()]) == "Bought · 1 book · $7.80"
    assert list_view.bought_total([a_purchase(), a_purchase(paid=gbp)]) == (
        "Bought · 2 books"
    )
    assert list_view.bought_total([]) is None

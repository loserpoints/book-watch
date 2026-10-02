"""The book page's values for the system's pieces (S34, #98).

Nothing here is a new rule. These check that each rule already decided is
written down the way Alan chose: over by an amount, a floor with a + when
shipping is unknown, and a currency we cannot compare said so.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from book_watch.copies import Copy
from book_watch.ebay.search import Money
from book_watch.standing import Market, Standing
from book_watch.web import book_view
from book_watch.web.filters import since

LIMIT = Money(Decimal("12.00"), "USD")


def a_copy(price="27.00", shipping="0.00", currency="USD", **extra):
    return Copy(
        item_id="v1|1|0",
        title="Crash, a good copy",
        url="https://ebay/x",
        price=Money(Decimal(price), currency),
        shipping=Money(Decimal(shipping), currency) if shipping is not None else None,
        tier="certain",
        **extra,
    )


def row(copy, placed=None, ceiling=LIMIT, listed=None):
    return book_view.copy_row(
        copy, copy.against(ceiling), placed, ceiling, listed or {}
    )


def test_money_drops_cents_only_when_there_are_none():
    assert book_view.money(Money(Decimal("12.00"), "USD")) == "$12"
    assert book_view.money(Money(Decimal("10.49"), "USD")) == "$10.49"
    assert book_view.money(Money(Decimal("5.00"), "GBP")) == "£5"
    # No symbol we are sure of: the code, after, rather than a guess.
    assert book_view.money(Money(Decimal("5.50"), "AUD")) == "5.50 AUD"


def test_over_is_marked_without_saying_by_how_much():
    """S61: the strip shows where the limit sits, so the row says only over."""
    c = row(a_copy("27.00", "0.00"))

    assert c["verdict"] == "over"
    assert "over_by" not in c


def test_unknown_shipping_shows_the_price_and_no_verdict():
    """S54: even a price alone over the limit is left uncolored, with no
    amount over."""
    c = row(a_copy("14.00", None))

    assert c["verdict"] is None
    assert c["shipping_unknown"]
    assert c["price_text"] == "$14"


def test_under_carries_no_amount():
    assert row(a_copy("5.00", "2.00"))["verdict"] == "under"


def test_another_currency_is_left_uncolored():
    c = row(a_copy("5.00", "2.00", currency="GBP"))

    assert c["verdict"] is None
    assert c["price_text"] == "£7"
    assert not c["shipping_unknown"]


def test_a_copy_without_a_delivered_price_says_so_in_place_of_a_rank():
    """One reason, whatever produced it (S54)."""
    placed = Standing("used", unplaced="no delivered price")

    assert row(a_copy("5.00", None), placed)["place_text"] == (
        "can't place: no delivered price"
    )


def test_a_ranked_copy_is_drawn_among_its_peers():
    listed = {("used", "USD"): [Decimal("27.00"), Decimal("30.00")]}
    placed = Standing("used", rank=1, listed=2)

    c = row(a_copy(condition_id="5000"), placed=placed, listed=listed)

    assert "1 of 2 by price" in c["place"]
    assert c["place_text"] is None


def test_the_only_copy_of_its_kind_keeps_its_words():
    c = row(a_copy(condition_id="1000"), placed=Standing("new", rank=1, listed=1))

    assert c["place_text"] == "only new listing"


def test_a_market_names_both_populations_only_when_they_differ():
    seen = {("used", "USD"): [Decimal("4"), Decimal("9"), Decimal("30")]}
    wider = Market(
        "used",
        listed=2,
        seen=3,
        low=Money(Decimal("4"), "USD"),
        high=Money(Decimal("30"), "USD"),
    )
    same = Market(
        "used",
        listed=3,
        seen=3,
        low=Money(Decimal("4"), "USD"),
        high=Money(Decimal("30"), "USD"),
    )

    assert book_view.market_line(wider, seen, LIMIT)["text"] == (
        "2 used listed now, 3 seen"
    )
    line = book_view.market_line(same, seen, LIMIT)
    assert line["text"] == "3 used listed now"
    # The limit is drawn on the strip, as the dashed guide.
    assert "strip-limit" in line["strip"]


def test_since_is_short_enough_for_a_chip():
    now = datetime.now(UTC)
    assert since(now) == "just now"
    assert since(now - timedelta(minutes=4)) == "4m"
    assert since(now - timedelta(hours=2)) == "2h"
    assert since(now - timedelta(days=3)) == "3d"
    assert since(now - timedelta(weeks=3)) == "3w"
    assert since(now - timedelta(days=300)) == "9mo"
    assert since(None) == "never"


def test_a_copy_that_takes_offers_is_marked_and_keeps_its_verdict():
    """Best Offer is shown, never counted: the asking price is still over."""
    marked = row(a_copy(takes_offers=True))

    assert marked["takes_offers"]
    assert marked["verdict"] == "over"
    assert not row(a_copy())["takes_offers"]

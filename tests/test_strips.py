"""The price strips: dots on one scale, and a range labeled in whole dollars."""

import re
from decimal import Decimal

from book_watch.web import strips


def positions(svg, cls):
    return [float(x) for x in re.findall(rf'class="{cls}" cx="([\d.]+)"', svg)]


def test_prices_sit_on_one_scale_between_the_padded_ends():
    svg = strips.range_strip([10, 20, 30], width=110, labeled=False)

    # 5px pad each side leaves 100px for a $20 span: $10 per 50px.
    assert positions(svg, "strip-dot") == [5.0, 55.0, 105.0]


def test_the_limit_widens_the_scale_when_it_lies_outside_the_prices():
    svg = strips.range_strip([10, 20], limit=30, width=110, labeled=False)

    assert positions(svg, "strip-dot") == [5.0, 55.0]
    assert 'class="strip-limit" x1="105.0"' in svg


def test_the_ends_are_labeled_in_whole_dollars():
    svg = strips.range_strip([Decimal("10.49"), Decimal("26.5")])

    assert ">$10</text>" in svg
    assert ">$27</text>" in svg


def test_every_dot_on_the_range_strip_is_the_same():
    """The cheapest is always the left end, so emphasizing it says nothing."""
    svg = strips.range_strip([10, 12, 27])

    assert set(re.findall(r'<circle class="([\w-]+)"', svg)) == {"strip-dot"}


def test_the_rank_strip_marks_this_copy_among_the_others():
    svg = strips.rank_strip([10.49, 12, 27], 12, width=64)

    assert len(positions(svg, "strip-peer")) == 2
    assert len(positions(svg, "strip-mine")) == 1
    assert 'aria-label="2 of 3 by price' in svg


def test_a_single_copy_has_no_rank_strip():
    """One dot on a line says nothing; the row says "only new listing" instead."""
    assert strips.rank_strip([19], 19) == ""


def test_one_price_sits_in_the_middle_rather_than_dividing_by_zero():
    svg = strips.range_strip([12], width=110, labeled=False)

    assert positions(svg, "strip-dot") == [55.0]


def test_the_strip_says_what_it_shows_to_a_screen_reader():
    svg = strips.range_strip([10.49, 12, 27])

    assert 'aria-label="3 asking prices seen, $10 to $27"' in svg

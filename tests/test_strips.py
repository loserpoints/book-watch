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


def test_a_limit_outside_the_prices_leaves_the_scale_to_the_prices():
    """S61: the scale no longer stretches to reach the limit, so a limit far
    below every price cannot squeeze the dots and their labels together."""
    svg = strips.range_strip([10, 20], limit=30, width=110, labeled=False)

    assert positions(svg, "strip-dot strip-dot-under") == [5.0, 105.0]


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


# --- the limit (S61) ---------------------------------------------------------


def dots(svg):
    return re.findall(r'class="strip-dot ?([a-z-]*)"', svg)


def test_each_dot_is_judged_like_a_price():
    svg = strips.range_strip([8, 10, 14], limit=10)

    assert dots(svg) == ["strip-dot-under", "strip-dot-under", "strip-dot-over"]


def test_without_a_limit_the_dots_are_left_unjudged():
    svg = strips.range_strip([8, 14])

    assert dots(svg) == ["", ""]
    assert "strip-limit" not in svg


def test_the_limit_is_drawn_when_it_falls_among_the_prices():
    svg = strips.range_strip([10, 20, 30], limit=15, width=110, labeled=False)

    assert 'class="strip-limit" x1="30.0"' in svg


def test_the_limit_is_drawn_at_either_end_of_the_prices():
    for limit in (10, 30):
        assert "strip-limit" in strips.range_strip([10, 20, 30], limit=limit)


def test_a_limit_outside_the_prices_draws_no_line():
    """No line with a ✓ means every copy is under; no line without one means
    every copy is over. Either way the reading needs no color."""
    for limit in (9, 31):
        assert "strip-limit" not in strips.range_strip([10, 20, 30], limit=limit)


def test_the_strip_says_how_many_prices_are_under_the_limit():
    svg = strips.range_strip([8, 10, 14], limit=Decimal("10.49"))

    assert "2 at or under the limit of $10" in svg

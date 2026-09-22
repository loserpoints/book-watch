"""Tests for ISBN validation.

The check digit is the whole point: it is what separates "you mistyped" from
"that is a book", without asking anybody's catalogue.
"""

import pytest

from book_watch.isbn import normalise

# Crash, Vintage. The same book, spelled four ways.
CRASH_13 = "9780099448396"


@pytest.mark.parametrize(
    "typed",
    [
        CRASH_13,
        "978-0-09-944839-6",
        "978 0 09 944839 6",
        "  9780099448396  ",
        "0099448394",  # the ISBN-10 of the same book
        "0-09-944839-4",
    ],
)
def test_every_spelling_of_one_book_normalises_to_one_value(typed):
    """Otherwise the want-list could hold the same book twice."""
    assert normalise(typed) == CRASH_13


def test_an_isbn10_check_digit_of_x_is_understood():
    """X means ten. A tenth of valid ISBN-10s end in one."""
    assert normalise("043942089X") == "9780439420891"


@pytest.mark.parametrize(
    "typed",
    [
        "9780099448390",  # last digit wrong
        "9780099448396x",  # trailing junk
        "0099448395",  # ISBN-10, last digit wrong
    ],
)
def test_a_wrong_check_digit_is_rejected(typed):
    assert normalise(typed) is None


@pytest.mark.parametrize(
    "typed",
    ["", "   ", "not an isbn", "12345", "97800994483961234", "X099448394"],
)
def test_things_that_are_not_isbns_are_rejected(typed):
    assert normalise(typed) is None


def test_every_single_digit_typo_is_caught():
    """A mod-10 check digit catches all single-digit errors. That is the
    guarantee this validation rests on."""
    changed = [
        CRASH_13[:i] + str(d) + CRASH_13[i + 1 :]
        for i in range(13)
        for d in range(10)
        if str(d) != CRASH_13[i]
    ]

    assert len(changed) == 117
    assert all(normalise(typo) is None for typo in changed)


def test_swapping_two_adjacent_digits_that_differ_by_five_is_not_caught():
    """A real hole in ISBN-13, documented rather than papered over.

    The weights alternate 1 and 3, so swapping neighbours changes the total by
    twice the difference between them. When that difference is 5 the total
    moves by 10 and the check digit does not notice. Every other adjacent
    transposition is caught.

    This is why validation is a guard and not a guarantee: it makes a typo
    unlikely to survive, not impossible. The override exists partly because a
    check digit can be wrong in both directions.
    """
    missed = [
        swapped
        for i in range(12)
        if CRASH_13[i] != CRASH_13[i + 1]
        for swapped in [
            CRASH_13[:i] + CRASH_13[i + 1] + CRASH_13[i] + CRASH_13[i + 2 :]
        ]
        if normalise(swapped) is not None
    ]

    assert missed == ["9780094948396", "9780099443896"]
    assert all(
        abs(int(m[i]) - int(m[i + 1])) == 5 for m, i in zip(missed, (6, 9), strict=True)
    )

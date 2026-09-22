"""Validating and normalising ISBNs.

Arithmetic only. This checks that a number *is* an ISBN — that its check digit
agrees with the rest of it — and says nothing about whether a book with that
ISBN exists. Those are different questions with different answers, and only the
first one can be answered without asking somebody else's catalogue.

Everything is stored as ISBN-13. A book with both a 10 and a 13 has one
identity, and keeping two spellings of it would mean a want-list that can hold
the same book twice without noticing.
"""

from __future__ import annotations

import re

#: Sellers, spines and copy-paste all disagree about separators.
_SEPARATORS = re.compile(r"[\s\-–—]+")

#: The prefix ISBN-10s are promoted with. 979 exists but no ISBN-10 maps to it.
_ISBN13_PREFIX = "978"


def tidy(raw: str) -> str:
    """Strip separators and normalise case, without judging the result."""
    return _SEPARATORS.sub("", raw.strip()).upper()


def normalise(raw: str) -> str | None:
    """Return `raw` as a valid ISBN-13, or `None` if it is not an ISBN.

    Accepts either length and returns one, so callers never have to care which
    was typed.
    """
    candidate = tidy(raw)
    if len(candidate) == 10 and _isbn10_is_valid(candidate):
        return _to_isbn13(candidate)
    if len(candidate) == 13 and _isbn13_is_valid(candidate):
        return candidate
    return None


def _isbn10_is_valid(candidate: str) -> bool:
    """Weighted sum, 10 down to 1, divisible by 11. Only the last digit may be X."""
    if not re.fullmatch(r"\d{9}[\dX]", candidate):
        return False
    total = sum(
        (10 - position) * (10 if char == "X" else int(char))
        for position, char in enumerate(candidate)
    )
    return total % 11 == 0


def _isbn13_is_valid(candidate: str) -> bool:
    """Digits alternately weighted 1 and 3, divisible by 10."""
    if not candidate.isdigit():
        return False
    total = sum(
        int(char) * (1 if position % 2 == 0 else 3)
        for position, char in enumerate(candidate)
    )
    return total % 10 == 0


def _to_isbn13(isbn10: str) -> str:
    body = _ISBN13_PREFIX + isbn10[:9]
    total = sum(
        int(char) * (1 if position % 2 == 0 else 3)
        for position, char in enumerate(body)
    )
    return body + str((10 - total % 10) % 10)

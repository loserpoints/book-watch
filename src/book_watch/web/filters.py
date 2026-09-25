"""Words for numbers, shared by every screen that shows them.

These live apart from any one router because two screens now say the same
things: the book page and the want-list both report how long ago a book was
checked, and a reader who saw "4 minutes ago" on one and a timestamp on the
other would reasonably wonder whether they meant the same thing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from jinja2 import Environment


def register(env: Environment) -> None:
    """Add these filters to a template environment."""
    env.filters["ago"] = ago
    env.filters["ordinal"] = ordinal


def ordinal(n: int) -> str:
    """1 -> "1st", 2 -> "2nd", 11 -> "11th".

    Display only, which is why it lives here rather than beside the numbers.
    The teens are the whole reason this is not a lookup on the last digit.
    """
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def ago(when: datetime | None) -> str:
    """How long ago, in words a person reads at a glance.

    "checked 2026-09-23 20:48:08" tells you nothing without arithmetic, which
    is the point of issue #22. This is the part of it this slice needs: the
    page's whole claim is about how current its results are, so the one number
    that matters must not need working out.
    """
    if when is None:
        return "never"
    seconds = (datetime.now(UTC) - when).total_seconds()
    if seconds < 90:
        return "just now"
    for size, unit in ((60, "minute"), (3600, "hour"), (86400, "day")):
        count = int(seconds // size)
        if count < size_of_next(unit):
            return f"{count} {unit}{'' if count == 1 else 's'} ago"
    weeks = max(1, int(seconds // 604800))
    return f"{weeks} week{'' if weeks == 1 else 's'} ago"


def size_of_next(unit: str) -> int:
    """How many of `unit` fit before the next unit up takes over."""
    return {"minute": 60, "hour": 24, "day": 14}[unit]

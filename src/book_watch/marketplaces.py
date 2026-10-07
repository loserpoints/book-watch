"""Which marketplace a listing is on, and the facts that have to mean the same
thing whichever one it is.

A listing is identified by its marketplace and its id there, never by what its
id looks like. Condition is stored on eBay's scale for every marketplace, so
each copy's condition tag reads one column. See
docs/rules/matching.md.
"""

from __future__ import annotations

from typing import Literal

Marketplace = Literal["ebay", "abebooks"]

#: How each marketplace is named to Alan, on screen and in the email.
NAMES: dict[str, str] = {"ebay": "eBay", "abebooks": "AbeBooks"}

#: eBay's condition ids for the grades a book can carry.
NEW = "1000"
#: Secondhand, no grade stated.
USED = "3000"
LIKE_NEW = "2750"
VERY_GOOD = "4000"
GOOD = "5000"
ACCEPTABLE = "6000"

#: The one name each grade is shown by, whatever words the seller or the
#: marketplace used (S70, #247). eBay's own listings say "New" for one seller
#: and "Brand New" for another, and AbeBooks says "New": a bare "New" also
#: reads as the "new" a copy carries when it appeared since the last visit.
GRADE_NAMES: dict[str, str] = {
    NEW: "Brand New",
    LIKE_NEW: "Like New",
    VERY_GOOD: "Very Good",
    GOOD: "Good",
    ACCEPTABLE: "Acceptable",
    USED: "Used",
}


def condition_name(condition_id: str | None, words: str | None) -> str:
    """What a copy's condition tag says: its grade's one name, or the seller's
    words for a grade without one, or that nothing was stated."""
    if condition_id in GRADE_NAMES:
        return GRADE_NAMES[condition_id]
    return words or "condition unstated"


#: AbeBooks' condition words onto eBay's ids. The booksellers' scale runs
#: As New, Fine, Near Fine, Very Good, Good, Fair, Poor. Near Fine maps down
#: to Very Good, so a grade undersells rather than oversells.
_ABEBOOKS_CONDITION = {
    "new": NEW,
    "as new": LIKE_NEW,
    "fine": LIKE_NEW,
    "near fine": VERY_GOOD,
    "very good": VERY_GOOD,
    "good": GOOD,
    "fair": ACCEPTABLE,
    "poor": ACCEPTABLE,
}


def abebooks_condition_id(words: str | None) -> str | None:
    """eBay's condition id for AbeBooks' words, or None when they say nothing.

    AbeBooks writes "New", "Used - Very good" or just "Used". The grade is the
    part after the dash. "Used" alone states no grade, and is eBay's generic
    Used: secondhand, counted in the used market, without claiming a grade.
    """
    if not words:
        return None
    grade = words.split(" - ", 1)[-1].strip().lower()
    if grade == "used":
        return USED
    return _ABEBOOKS_CONDITION.get(grade)


def is_us(located_in: str | None) -> bool:
    """Whether a copy's seller is in the US, from its two-letter country code."""
    return located_in == "US"

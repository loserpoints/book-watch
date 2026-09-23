"""Decide how confident we are that a listing is the book being watched.

Pure logic. Nothing here opens a socket, reads a database or knows what a
marketplace is — it is handed what is known about one listing and answers with
a tier. That makes it testable against the 227 hand-labelled listings in
`tests/data/`, which is the only reason the numbers in decision 33 are
verifiable rather than remembered.

**Nothing is rejected for being uncertain.** Decision 33 measured that every
rule available is good at one question and bad at the other: listing text
finds the book and cannot find the edition, `epid` finds the edition and
misses two thirds of the copies. They fail in opposite directions, so they are
layers rather than candidates, and the uncertainty is carried in the tier
instead of being resolved by throwing listings away. Recall was 100% on both
hunts on both books precisely because of that.

The two hunts are this one function with **one** parameter: which numbers count
as the target. Decision 33 said two, adding a stricter text floor for a
collector, and the corpus in `tests/data/` disproved it — that book had no
declared numbers at all, so S6 never scored it on the collector's hunt and
never saw that the stricter floor hides true matches. See the amendment to
decision 33.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from book_watch.wantlist import Hunt

#: How sure we are, worst case first when read upwards.
#:
#: `probable` is reachable only on a collector's hunt, where a listing's `epid`
#: says one edition and the seller's own declared number says another. Neither
#: identifier wins, so the listing is shown saying so.
Tier = Literal["certain", "probable", "possible", "excluded"]

#: Words too common to carry a title. Kept deliberately tiny: a longer list
#: starts discarding real words ("The Crystal World" is not "Crystal World"),
#: and the measured errors were never caused by these.
_NOISE = frozenset({"the", "a", "an", "and"})


@dataclass(frozen=True, slots=True)
class Target:
    """The book being hunted, and the identifiers known to belong to it.

    `isbns` is every number we have learned is this book — one for a
    collector's hunt, and however many listings have taught us for a reader's.
    It is knowledge that accumulates, never a list downloaded up front:
    decision 7 as amended measured that about 80% of a downloaded edition list
    is never offered for sale.

    No author. It narrows the *search* — an entry looks a marketplace up by
    title and author together — but by the time a listing is being graded that
    filtering has already happened, and adding it here changed no answers.
    """

    title: str
    isbns: frozenset[str] = field(default_factory=frozenset)
    epids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything known about one listing that bears on what it is.

    Deliberately not an eBay type. A second marketplace would fill this in
    from its own shapes and the rule would not change.

    `identity` is what our notebook says the seller's declared number is —
    Open Library's title for it. `None` covers both "Open Library has no
    record of this number" and "nobody has asked yet", and decision 33
    requires those behave identically: neither may exclude a listing. Every
    unresolvable number in the measured sample was a non-English edition of
    the right book, and a listing whose number has not been looked up yet is
    simply one whose turn has not come.
    """

    listing_title: str
    epid: str | None = None
    declared_isbn: str | None = None
    identity: str | None = None


def grade(evidence: Evidence, target: Target, *, hunt: Hunt = "reader") -> Tier:
    """How confident are we that this listing is what we are looking for?

    Identifiers first, in decreasing order of trust, and text only as a floor.
    Text alone never produces `certain`: on the edition question it scored 36%
    precision, and on *Crash* it collapsed to 12%.
    """
    declared = evidence.declared_isbn

    if declared and declared in target.isbns:
        return "certain"

    if declared and evidence.identity is not None:
        # We asked, and the catalogue answered. If it named a different book,
        # that is the strongest negative signal available — it is the only
        # thing that catches an omnibus, whose title contains the book's and
        # whose author is the right one.
        if not _names_the_same_book(evidence.identity, target.title):
            return "excluded"
        # It named this book, under a number we had not connected to it yet.
        # For a reader that settles it. For a collector it is the wrong
        # printing, and an `epid` claiming otherwise is a disagreement rather
        # than a confirmation.
        if hunt == "reader":
            return "certain"
        return "probable" if _epid_matches(evidence, target) else "excluded"

    if _epid_matches(evidence, target):
        return "certain"

    # The floor, and it is the same floor for both hunts. Requiring the
    # author's name here looked like the right extra caution for a collector
    # and cost two true matches on the one book in the corpus whose sellers
    # never type a number — both listed as plainly as "Pride and Prejudice".
    # Loosening it hid nothing and raised that book's precision from 10% to
    # 12%, because the listings it lets in are mostly ones already being shown.
    if _text_matches(evidence.listing_title, target):
        return "possible"

    return "excluded"


def _epid_matches(evidence: Evidence, target: Target) -> bool:
    return evidence.epid is not None and evidence.epid in target.epids


def _names_the_same_book(identity: str, wanted: str) -> bool:
    """Is what the catalogue called this number the book we are after?

    Equal, or the wanted title followed by more words: *Crash: A Novel* and
    *Stoner (Korean Edition)* are the book, *John Williams : Collected Novels*
    is a box that contains it.

    Comparing what Open Library called the number, rather than which work it
    filed it under. Decision 33: *Crash* sits under five separate work ids and
    *Stoner* under five, and a rule built on work-id equality threw away 21 of
    the 45 true *Crash* listings.
    """
    found, looking_for = _flatten(identity), _flatten(wanted)
    return found == looking_for or found.startswith(looking_for + " ")


def _text_matches(
    listing_title: str, target: Target, *, with_author: bool = False
) -> bool:
    text = _flatten(listing_title)
    words = [w for w in _flatten(target.title).split() if w not in _NOISE]
    if not words or not all(word in text for word in words):
        return False
    if not with_author:
        return True
    if not target.author:
        return True
    return _surname(target.author) in text


def _surname(author: str) -> str:
    """The last word of a name, which is the part a listing reliably carries.

    "J. G. Ballard" appears as Ballard, J G Ballard, JG Ballard and
    J.G. Ballard across the measured sample. Only the surname survives all of
    them.
    """
    parts = _flatten(author).split()
    return parts[-1] if parts else ""


def _flatten(text: str) -> str:
    """Lowercase, with every run of non-alphanumerics becoming one space.

    So "J.G. Ballard", "J G Ballard" and "JG  Ballard" all reduce alike, and
    "Crash: A Novel" starts with "crash".
    """
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

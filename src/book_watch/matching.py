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

    `author` is used only to rule a listing **out**. It was left out entirely
    at first, on a measurement saying it changed no answers — taken across
    three books whose titles are effectively unique in the catalogue, so the
    sample could not show the failure. Three different books called *Breaking
    and Entering* then graded certain against each other in production. A
    title is not a book.
    """

    title: str
    author: str | None = None
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
    #: The author the seller declared. Present on about nine listings in ten,
    #: prefilled by eBay where its catalogue matched the listing and typed
    #: otherwise — a claim about the copy, not a fact about the edition.
    declared_author: str | None = None


def grade(evidence: Evidence, target: Target, *, hunt: Hunt = "reader") -> Tier:
    """How confident are we that this listing is what we are looking for?

    Identifiers first, in decreasing order of trust, and text only as a floor.
    Text alone never produces `certain`: on the edition question it scored 36%
    precision, and on *Crash* it collapsed to 12%.
    """
    declared = evidence.declared_isbn

    if declared and declared in target.isbns:
        # The number being watched. A seller who also typed the wrong author
        # has made a typing mistake, not sold a different book.
        return "certain"

    if _author_contradicts(evidence, target):
        return "excluded"

    if declared and evidence.identity is not None:
        # We asked, and the catalogue answered. If it named a different book,
        # that is the strongest negative signal available — it is the only
        # thing that catches an omnibus, whose title contains the book's and
        # whose author is the right one.
        if not names_the_same_book(evidence.identity, target.title):
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


def _author_contradicts(evidence: Evidence, target: Target) -> bool:
    """Does the seller say this is by somebody else?

    Only ever a negative. Two names agreeing proves nothing — every listing
    for a famous title names its famous author — but two disagreeing is the
    one cheap signal that a matching title is a different book.

    Both sides have to be known. A listing that declared no author contradicts
    nothing, and neither does a want-list entry added before authors were
    asked for.

    **And the listing's own name must not vouch for the author either.** The
    corpus insisted on this: requiring only that the two names agree hid a
    real copy of *Stoner* whose seller had typed the translator's name into
    the author field, and a real copy of *Crash* whose seller had typed "NA".
    Both listings said "Williams" and "Ballard" plainly in their titles.

    So this rejects only when two independent things fail to mention the
    author — which is what the three books called *Breaking and Entering*
    looked like, and what a mistyped author field does not.
    """
    if not target.author or not evidence.declared_author:
        return False
    wanted = surnames(target.author)
    claimed = surnames(evidence.declared_author)
    if not wanted or not claimed or wanted & claimed:
        return False
    return _surname(target.author) not in _flatten(evidence.listing_title)


def surnames(names: str) -> set[str]:
    """Every word of a name field, which may hold several names.

    Sellers write "Williams, John Edward; McGahern, John (INT)" where eBay's
    catalogue writes "Joy Williams", so positions cannot be relied on. Keeping
    every word is deliberately generous, because this decides whether to
    *reject*: a false agreement costs one wrong listing shown, a false
    disagreement costs a right one hidden.

    Single letters go, so "J. G. Ballard" does not agree with "J. K. Rowling".
    """
    return {word for word in _flatten(names).split() if len(word) > 1}


def _surname(author: str) -> str:
    """The last word of a name — the part a listing carries intact.

    "J. G. Ballard" appears as Ballard, J G Ballard, JG Ballard and
    J.G. Ballard across the measured sample, and only the last word survives
    all of them.
    """
    parts = surnames(author)
    ordered = [w for w in _flatten(author).split() if w in parts]
    return ordered[-1] if ordered else ""


def _epid_matches(evidence: Evidence, target: Target) -> bool:
    return evidence.epid is not None and evidence.epid in target.epids


def names_the_same_book(identity: str, wanted: str) -> bool:
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


def _text_matches(listing_title: str, target: Target) -> bool:
    """Does the listing name carry every significant word of the title?

    The weakest signal there is, and the reason text alone never reaches
    `certain`: on the edition question it scored 36% precision overall and 12%
    on *Crash*, because sellers list an author's famous titles and every
    Ballard listing mentions *Crash*.

    No author here. The stricter version was dropped in S10 when the corpus
    showed it hid true matches — listings named as plainly as "Pride and
    Prejudice" — and the author now does its work in `_author_contradicts`,
    where a *disagreement* rejects rather than an absence failing to admit.
    """
    text = _flatten(listing_title)
    words = [w for w in _flatten(target.title).split() if w not in _NOISE]
    return bool(words) and all(word in text for word in words)


def _flatten(text: str) -> str:
    """Lowercase, with every run of non-alphanumerics becoming one space.

    So "J.G. Ballard", "J G Ballard" and "JG  Ballard" all reduce alike, and
    "Crash: A Novel" starts with "crash".
    """
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

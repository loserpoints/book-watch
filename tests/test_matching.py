"""Tests for the grader, including the numbers it is supposed to produce.

The second half of this file scores every rule against 227 eBay listings that
were hand-classified twice by the person who would have bought them, during
S6. Those numbers are decision 33's whole argument, and until now they lived
in a decision record and in memory. Here they are assertions, so a change that
quietly degrades matching fails the build rather than shipping.

The thresholds are deliberately a little below what the rule achieves today.
A test that pins the exact number fails on every harmless change and gets
loosened until it means nothing; one that pins the claim fails only when the
claim stops being true.
"""

import json
from pathlib import Path

import pytest

from book_watch.matching import Evidence, Target, grade

CRASH = Target(
    title="Crash",
    isbns=frozenset({"9780374524128"}),
    epids=frozenset({"139663"}),
)

CORPUS = json.loads(
    (Path(__file__).parent / "data" / "labelled_listings.json").read_text()
)


# --- what each signal does --------------------------------------------------


def test_the_declared_number_being_the_one_wanted_settles_it():
    listing = Evidence("some seller's title", declared_isbn="9780374524128")

    assert grade(listing, CRASH) == "certain"


def test_a_matching_product_id_settles_it_too():
    listing = Evidence("Crash", epid="139663")

    assert grade(listing, CRASH) == "certain"


def test_a_number_the_catalogue_says_is_this_book_settles_it_for_a_reader():
    """A different printing, which is exactly what a reader will take."""
    listing = Evidence(
        "Crash by J.G. Ballard", declared_isbn="9780099448396", identity="Crash"
    )

    assert grade(listing, CRASH, hunt="reader") == "certain"


def test_the_same_number_is_the_wrong_printing_for_a_collector():
    listing = Evidence(
        "Crash by J.G. Ballard", declared_isbn="9780099448396", identity="Crash"
    )

    assert grade(listing, CRASH, hunt="collector") == "excluded"


def test_two_identifiers_disagreeing_is_probable_rather_than_certain():
    """The product id says this printing, the seller's own number says another."""
    listing = Evidence(
        "Crash",
        epid="139663",
        declared_isbn="9780099448396",
        identity="Crash",
    )

    assert grade(listing, CRASH, hunt="collector") == "probable"


def test_a_number_naming_a_different_book_excludes_the_listing():
    """The omnibus. Its title contains the book's and its author is the right one,
    so every other signal admits it."""
    stoner = Target(title="Stoner", isbns=frozenset({"9781590171998"}))
    listing = Evidence(
        "John Williams Collected Novels: Butcher's Crossing / Stoner / Augustus",
        declared_isbn="9781598537024",
        identity="John Williams : Collected Novels",
    )

    assert grade(listing, stoner) == "excluded"


def test_a_title_the_catalogue_extends_is_still_the_book():
    """*Crash: A Novel* is the book. *Stoner (Korean Edition)* is too."""
    listing = Evidence(
        "Crash", declared_isbn="9781250171511", identity="Crash: A Novel"
    )

    assert grade(listing, CRASH, hunt="reader") == "certain"


def test_text_alone_never_reaches_certain():
    """It scored 36% precision on the edition question, and 12% on this book."""
    listing = Evidence("Crash by J. G. Ballard, first edition")

    assert grade(listing, CRASH) == "possible"


def test_a_listing_naming_a_different_book_entirely_is_excluded():
    listing = Evidence("Concrete Island by J. G. Ballard")

    assert grade(listing, CRASH) == "excluded"


def test_a_number_that_did_not_resolve_does_not_exclude_anything():
    """Decision 33. Every unresolvable number in the sample was a non-English
    edition of the right book, and one nobody has asked about yet is simply
    waiting its turn. Both arrive here as no identity at all."""
    listing = Evidence(
        "Crash; J.G. Ballard; Edition Phantasia; Limited edition",
        declared_isbn="9783924959029",
        identity=None,
    )

    assert grade(listing, CRASH) == "possible"


def test_punctuation_and_spacing_do_not_decide_anything():
    pride = Target(title="Pride and Prejudice")

    assert grade(Evidence("PRIDE & PREJUDICE - Austen"), pride) == "possible"
    assert grade(Evidence("Pride  and   Prejudice!"), pride) == "possible"


# --- the corpus -------------------------------------------------------------


def scored(book: str, hunt: str, truth: str):
    """Grade every labelled listing for one book, and count how it went."""
    meta = CORPUS["books"][book]
    target = Target(
        title=meta["title"],
        author=meta["author"],
        isbns=frozenset({meta["isbn"]}),
        epids=frozenset({meta["epid"]}),
    )
    tiers: dict[str, list[str]] = {}
    wanted = hidden = 0
    for row in CORPUS["listings"]:
        if row["book"] != book:
            continue
        tier = grade(
            Evidence(
                row["listing_title"],
                row["epid"],
                row["declared_isbn"],
                row["identity_title"],
                row.get("declared_author"),
            ),
            target,
            hunt=hunt,
        )
        # "unsure" was a real answer on two listings and is not rounded into a
        # number here; it counts towards neither precision nor recall.
        if row[truth] == "unsure":
            continue
        tiers.setdefault(tier, []).append(row[truth])
        wanted += row[truth] == "yes"
        hidden += tier == "excluded" and row[truth] == "yes"
    return tiers, wanted, hidden


def precision(tiers, tier) -> float:
    rows = tiers.get(tier, [])
    return 100 * sum(1 for r in rows if r == "yes") / len(rows) if rows else 0.0


BOOKS = ["pride-and-prejudice", "crash", "stoner"]


def test_the_corpus_is_what_it_says_it_is():
    """If this drifts, every number below is measuring something else."""
    assert len(CORPUS["listings"]) == 227
    assert sorted(CORPUS["books"]) == sorted(BOOKS)


@pytest.mark.parametrize("book", BOOKS)
@pytest.mark.parametrize("hunt", ["reader", "collector"])
def test_nothing_true_is_ever_hidden(book, hunt):
    """The property the whole design exists for.

    Decision 33 chose grading over filtering precisely so that recall stays
    complete — an uncertain listing is labelled uncertain and shown lower
    down, never discarded. This is the assertion that keeps that true.
    """
    _, wanted, hidden = scored(
        book, hunt, "is_book" if hunt == "reader" else "is_edition"
    )

    assert hidden == 0, f"{hidden} of {wanted} real matches were excluded"


@pytest.mark.parametrize(
    ("book", "floor"),
    [("pride-and-prejudice", 95), ("crash", 92), ("stoner", 98)],
)
def test_a_reader_can_trust_the_certain_tier(book, floor):
    tiers, _, _ = scored(book, "reader", "is_book")

    assert precision(tiers, "certain") >= floor


@pytest.mark.parametrize(
    ("book", "floor"), [("pride-and-prejudice", 90), ("stoner", 92)]
)
def test_a_collector_can_mostly_trust_the_certain_tier(book, floor):
    """*Crash* is left out on purpose: six right-edition listings is not a
    sample, and decision 33 records that its `epid` over-merges. Pinning a
    number to it would be pinning noise."""
    tiers, _, _ = scored(book, "collector", "is_edition")

    assert precision(tiers, "certain") >= floor


@pytest.mark.parametrize("book", BOOKS)
def test_the_certain_tier_is_worth_having(book):
    """Not just accurate — big enough to be the list a reader actually reads."""
    tiers, wanted, _ = scored(book, "reader", "is_book")

    assert len(tiers.get("certain", [])) >= 0.3 * wanted


def test_identifiers_beat_text_where_it_matters_most():
    """The finding decision 33 turns on, as a test rather than a memory.

    Text finds the book and cannot find the edition. Identifiers find the
    edition. They fail in opposite directions, which is what makes them
    layers rather than competitors.
    """
    tiers, _, _ = scored("stoner", "collector", "is_edition")

    assert precision(tiers, "certain") >= 90
    assert precision(tiers, "possible") <= 40


# --- a title is not a book --------------------------------------------------


BREAKING = Target(title="Breaking and Entering", author="Joy Williams")


def test_a_same_titled_book_by_someone_else_is_excluded():
    """Found in production, not in the corpus.

    Three different books are called *Breaking and Entering*. Open Library
    confirms each number is something by that name, which it is, so comparing
    titles alone graded all three certain against each other.
    """
    gillmor = Evidence(
        "Breaking and Entering - paperback Gillmor, Don",
        declared_isbn="9781771965231",
        identity="Breaking and Entering",
        declared_author="Don Gillmor",
    )

    assert grade(gillmor, BREAKING) == "excluded"


def test_the_right_book_by_the_right_author_still_passes():
    williams = Evidence(
        "Breaking and Entering - Paperback By Williams, Joy",
        declared_isbn="9780394757735",
        identity="Breaking and entering",
        declared_author="Joy Williams",
    )

    assert grade(williams, BREAKING) == "certain"


def test_a_seller_who_typed_the_translator_does_not_lose_the_listing():
    """The listing's own name vouches for the author, so one wrong field
    cannot hide it. This cost a real copy of *Stoner* before the rule
    required two independent signals to disagree."""
    italian = Evidence(
        "John Edward Williams Stefano Tummolini Stoner (Paperback) (UK IMPORT)",
        declared_isbn="9788804732495",
        declared_author="Stefano Tummolini",
    )
    stoner = Target(title="Stoner", author="John Williams")

    assert grade(italian, stoner) != "excluded"


def test_a_seller_who_typed_nothing_useful_does_not_lose_the_listing():
    """ "NA" is a placeholder, and the title says Ballard plainly."""
    crash = Evidence("Crash J.G. Ballard", declared_author="NA")

    assert grade(crash, Target(title="Crash", author="J. G. Ballard")) != "excluded"


def test_the_number_being_watched_survives_a_wrong_author():
    """A seller who typed the wrong author has mistyped, not sold another book."""
    listing = Evidence(
        "Crash",
        declared_isbn="9780374524128",
        declared_author="Somebody Else",
    )

    assert (
        grade(
            listing,
            Target(
                title="Crash",
                author="J. G. Ballard",
                isbns=frozenset({"9780374524128"}),
            ),
        )
        == "certain"
    )


def test_an_entry_with_no_author_rejects_nothing_on_that_basis():
    """Entries added before authors were asked for must not start failing."""
    gillmor = Evidence(
        "Breaking and Entering by Gillmor, Don",
        declared_isbn="9781771965231",
        identity="Breaking and Entering",
        declared_author="Don Gillmor",
    )

    assert grade(gillmor, Target(title="Breaking and Entering")) == "certain"

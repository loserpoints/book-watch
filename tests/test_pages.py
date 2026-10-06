"""Reading one AbeBooks or Biblio page: what it holds, and what is never asked for."""

from decimal import Decimal
from pathlib import Path

import pytest

from book_watch import pages

ISBN_PAGE = (Path(__file__).parent / "data" / "abebooks_isbn_page.html").read_text()


def test_an_isbn_page_gives_its_count_and_each_copy_delivered():
    page = pages.parse(ISBN_PAGE)

    assert page.result_count == 9
    assert [c.delivered for c in page.copies] == [
        Decimal("82.50"),
        Decimal("100.00"),
        Decimal("120.00"),
    ]


def test_a_large_count_says_over():
    page = pages.parse(ISBN_PAGE.replace("(9 results)", "(Over 1,500 results)"))

    assert page.result_count == 1500


def test_free_shipping_counts_as_no_shipping_cost():
    third = pages.parse(ISBN_PAGE).copies[2]

    assert third.price == Decimal("120.00")
    assert third.shipping == Decimal("0")


def test_each_copy_keeps_its_listing_id_and_first_edition():
    first = pages.parse(ISBN_PAGE).copies[0]

    assert first.listing_id == "32473927550"
    assert first.first_edition


def test_each_copy_keeps_its_isbn():
    copies = pages.parse(ISBN_PAGE).copies

    assert {c.isbn for c in copies} == {"9780670337286"}


def test_a_copy_without_an_isbn_says_so():
    row = (
        '<div data-srp-item-role="listing" data-csa-c-item-id="1">'
        "GERONIMO REX. Hannah, Barry. Published by Viking, 1972 Hardcover "
        "First Edition Condition: Fine US$ 75.00 US$ 5.75 shipping</div>"
    )

    copy = pages.parse(row).copies[0]

    assert copy.isbn is None
    assert copy.delivered == Decimal("80.75")


def test_a_bot_challenge_is_reported_rather_than_read_as_empty():
    challenge = "<html><head><title>Just a moment...</title></head></html>"

    page = pages.parse(challenge)

    assert page.challenged
    assert page.copies == []


@pytest.mark.parametrize(
    "url",
    [
        "https://www.abebooks.com/servlet/SearchResults?isbn=9780590353427",
        "https://www.abebooks.com/search/sortby/17/isbn/9780590353427",
        "https://www.biblio.com/search.php?keyisbn=9780590353427",
        "https://www.ebay.com/sch/i.html?_nkw=geronimo+rex",
        "http://www.abebooks.com/book-search/isbn/9780670337286/used/",
    ],
)
def test_pages_robots_disallow_and_other_sites_are_refused(url):
    with pytest.raises(pages.RefusedPath):
        pages.check_url(url)


def test_search_and_isbn_pages_are_allowed():
    pages.check_url("https://www.abebooks.com/book-search/isbn/9780670337286/used/")
    pages.check_url(
        "https://www.abebooks.com/book-search/title/geronimo-rex/author/barry-hannah/"
    )


def test_a_refused_page_sends_nothing(monkeypatch, capsys):
    def no_request(*args, **kwargs):
        raise AssertionError("a refused page must not be requested")

    monkeypatch.setattr(pages.httpx, "get", no_request)

    code = pages.main(["https://www.abebooks.com/servlet/SearchResults?isbn=1"])

    assert code == 2
    assert "robots.txt disallows /servlet/" in capsys.readouterr().err

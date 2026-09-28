"""The controls (S30, #110): what the markup promises the browser.

Behaviour that only a browser shows — focus returning to the opener, the back
gesture closing a sheet — is checked on a phone and recorded in the PR. What
is tested here is that the markup asks for it correctly.
"""

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch.web import assets, design, photos


def design_page() -> str:
    app = FastAPI()
    app.include_router(design.build_router())
    return TestClient(app).get("/design").text


# --- the enlarged photo -------------------------------------------------------


def test_an_ebay_photo_is_asked_for_at_the_largest_size():
    small = "https://i.ebayimg.com/images/g/abcDEF/s-l225.jpg"

    assert photos.larger(small) == "https://i.ebayimg.com/images/g/abcDEF/s-l1600.jpg"


def test_the_size_and_the_file_type_are_kept_apart():
    small = "https://i.ebayimg.com/images/g/x/s-l140.webp"

    assert photos.larger(small, 500) == "https://i.ebayimg.com/images/g/x/s-l500.webp"


def test_anything_not_shaped_like_an_ebay_photo_is_left_alone():
    """eBay's size convention is not a documented contract. A URL that does not
    match it is shown as it is, never rewritten into one that may not exist."""
    for url in (
        "https://example.com/s-l225.jpg",
        "https://i.ebayimg.com/thumbs/images/g/x/s-l225.jpg?set=1",
        "data:image/svg+xml;utf8,<svg/>",
        None,
        "",
    ):
        assert photos.larger(url) == url


def test_a_copy_photo_opens_the_enlarged_view_with_both_sizes():
    page = design_page()

    assert 'data-open="photo-view"' in page
    assert "data-photo=" in page and "data-photo-small=" in page
    assert '<dialog class="photo-view" id="photo-view"' in page


# --- sheets -------------------------------------------------------------------


def test_every_opener_points_at_a_dialog_on_the_page():
    page = design_page()
    targets = set(re.findall(r'data-open="([\w-]+)"', page))
    dialogs = set(re.findall(r'<dialog[^>]*\bid="([\w-]+)"', page))

    assert targets, "the design page should open at least one sheet"
    assert targets <= dialogs


def test_a_sheet_is_a_labelled_dialog():
    page = design_page()

    opening = '<dialog class="sheet" id="add-sheet"'
    assert f'{opening} aria-labelledby="add-sheet-title"' in page
    assert 'id="add-sheet-title"' in page


def test_the_check_all_sheet_offers_update_instead_of_cancel():
    """S27: the alternative on offer is the cheaper action, not a dead end."""
    sheet = design_page().split('id="check-sheet"')[1].split("</dialog>")[0]

    assert "Update 2" in sheet
    assert "Cancel" not in sheet


def test_the_switch_is_radios_so_it_needs_no_script():
    page = design_page()

    assert re.search(r'<input type="radio" name="way" value="title" checked>', page)
    assert re.search(r'<input type="radio" name="way" value="isbn">', page)


# --- fields and buttons -------------------------------------------------------


def test_every_field_has_a_visible_label():
    page = design_page()
    inputs = re.findall(r'<input id="([\w-]+)"', page)

    assert inputs
    for field_id in inputs:
        assert f'<label for="{field_id}">' in page, field_id


def test_an_optional_field_says_so():
    assert "(optional)" in design_page()


def test_the_script_is_served_with_its_version():
    assert re.search(r'src="/static/ui\.js\?v=[0-9a-f]{10}"', design_page())
    assert assets.version("ui.js")


def test_a_switched_side_is_never_laid_out_inline():
    """An inline `display` beats the rule that hides the side not chosen, so the
    switch shows both. The first draft of S30 did exactly that; a browser run,
    not a test, caught it."""
    assert not re.search(
        r'data-when="\w+"[^>]*style=|style=[^>]*data-when=', design_page()
    )

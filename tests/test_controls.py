"""The controls (S30, #110): what the markup promises the browser.

Behavior that only a browser shows — focus returning to the opener, the back
gesture closing a sheet — is checked on a phone and recorded in the PR. What
is tested here is that the markup asks for it correctly.
"""

import re
from pathlib import Path

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


def test_the_real_ebay_url_shape_is_the_one_enlarged():
    """Confirmed against a real one Alan sent: webp, at 1600 already. Enlarging
    it again must leave it as it is."""
    real = "https://i.ebayimg.com/images/g/O-QAAeSweGNqFIv6/s-l1600.webp"

    assert photos.larger(real) == real
    assert photos.larger(real.replace("s-l1600", "s-l225")) == real


def _copy_row(**copy) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(design.TEMPLATES_DIR), autoescape=True)
    assets.register(env)
    macro = env.from_string('{% import "_ui.html" as ui %}{{ ui.copy_row(c) }}')
    base = {"url": "#", "price_text": "$9", "verdict": "under", "condition": "Good"}
    return macro.render(c={**base, **copy})


def _photos_on(row: str) -> list[str]:
    import json

    found = re.search(r"data-photos='([^']*)'", row)
    assert found, "the photo button must carry every photo"
    return json.loads(found.group(1).replace("&#34;", '"'))


def test_every_photo_of_a_copy_goes_to_the_enlarged_view_largest_first():
    """S33. URLs only, in eBay's order; nothing is loaded until tapped."""
    small = "https://i.ebayimg.com/images/g/a/s-l225.jpg"
    row = _copy_row(
        photo_url=small,
        photos=[
            "https://i.ebayimg.com/images/g/a/s-l500.jpg",
            "https://i.ebayimg.com/images/g/b/s-l500.jpg",
        ],
    )

    assert _photos_on(row) == [
        "https://i.ebayimg.com/images/g/a/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/b/s-l1600.jpg",
    ]
    assert '<span class="photo-count" aria-hidden="true">2</span>' in row
    assert "one of 2" in row


def test_a_copy_not_yet_asked_about_since_s33_enlarges_its_one_photo():
    small = "https://i.ebayimg.com/images/g/a/s-l225.jpg"
    row = _copy_row(photo_url=small)

    assert _photos_on(row) == ["https://i.ebayimg.com/images/g/a/s-l1600.jpg"]
    assert "photo-count" not in row


def test_a_url_cannot_break_out_of_the_attribute():
    """The list is JSON inside a single-quoted attribute, so a quote in a URL
    has to arrive escaped rather than end it."""
    row = _copy_row(photo_url="https://x/a.jpg", photos=["https://x/it's.jpg"])

    assert "it's" not in row
    assert _photos_on(row) == ["https://x/it's.jpg"]


def test_no_photo_is_on_the_page_until_one_is_tapped():
    """The enlarged view holds no image until the script builds them."""
    page = design_page()
    dialog = re.search(r'<dialog class="photo-view".*?</dialog>', page, re.S)

    assert dialog and "<img" not in dialog.group(0)


# --- sheets -------------------------------------------------------------------


def test_every_opener_points_at_a_dialog_on_the_page():
    page = design_page()
    targets = set(re.findall(r'data-open="([\w-]+)"', page))
    dialogs = set(re.findall(r'<dialog[^>]*\bid="([\w-]+)"', page))

    assert targets, "the design page should open at least one sheet"
    assert targets <= dialogs


def test_a_sheet_is_a_labeled_dialog():
    page = design_page()

    opening = '<dialog class="sheet" id="add-sheet"'
    assert f'{opening} aria-labelledby="add-sheet-title"' in page
    assert 'id="add-sheet-title"' in page


def test_the_check_all_sheet_asks_before_searching_everything_again():
    """S69 (#217): Check all appears only when every book was checked within
    the hour, so the sheet's choice is to go ahead or not."""
    sheet = design_page().split('id="check-sheet"')[1].split("</dialog>")[0]

    assert "Check all 7" in sheet
    assert "Cancel" in sheet
    assert "Update" not in sheet


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
        # A setting's whole row is its label (S83), so it carries a class.
        assert re.search(rf'<label\b[^>]*\bfor="{field_id}"', page), field_id


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


def test_the_add_button_sits_above_every_other_layer():
    """S58: a want-list row's link and trash are stacked layers, and the +
    button floats over them. Any layer at or above it takes its taps."""
    css = (
        Path(__file__).parent.parent / "src/book_watch/web/static/app.css"
    ).read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    layers = {
        selector.strip(): int(z)
        for selector, body in rules
        for z in re.findall(r"z-index:\s*(-?\d+)", body)
    }
    fab = layers.pop(".fab", 0)

    assert all(z < fab for z in layers.values()), layers


def test_the_design_page_shows_a_copy_that_takes_offers():
    assert "takes offers" in design_page()


def test_every_pair_option_keeps_room_for_its_label_in_bold():
    """Choosing a side must not change a pair's width, or it reflows what sits
    beside it (S60). Each label is carried in `data-label`, which the
    stylesheet sets in bold, unseen, whether the option is a radio, a link,
    a button or the current word (S69)."""
    page = design_page()
    radios = re.findall(
        r'<label class="pair-option">.*?<span([^>]*)>([^<]*)</span>', page
    )
    others = re.findall(
        r'<(?:a|b|button)\b[^>]*class="pair-option"([^>]*)>([^<]*)</', page
    )

    assert radios and others
    for attributes, label in radios + others:
        assert f'data-label="{label}"' in attributes
    css = (Path(assets.STATIC_DIR) / "app.css").read_text()
    assert re.search(r"\.pair-option::after[^{]*\{[^}]*attr\(data-label\)", css)


def css_rules() -> dict[str, str]:
    """Each selector in the stylesheet, comments gone, with its declarations
    run together when it appears more than once."""
    css = (
        Path(__file__).parent.parent / "src/book_watch/web/static/app.css"
    ).read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules: dict[str, str] = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        for selector in selectors.split(","):
            key = " ".join(selector.split())
            rules[key] = rules.get(key, "") + body
    return rules


def z(body: str) -> int:
    found = re.findall(r"z-index:\s*(-?\d+)", body)
    return int(found[-1]) if found else 0


def test_a_copys_listing_link_covers_its_row(  # S73, #190
):
    """A tap anywhere on a copy opens its listing, as anywhere on a want-list
    row opens its book: the link stretches over the row it sits in."""
    rules = css_rules()

    assert "position: relative" in rules[".copy-row"]
    stretch = rules[".copy-listing::after"]
    assert "position: absolute" in stretch and "inset: 0" in stretch


def test_a_copys_own_controls_sit_above_its_link():
    """The photo, the note and the price caret keep their own taps. The photo's
    placeholder, a copy with none, isn't a control and stays under the link."""
    rules = css_rules()
    link = z(rules[".copy-listing::after"])

    for control in ("button.copy-photo", "details.copy-note", ".copy-row details.move"):
        assert z(rules[control]) > link, control
    assert z(rules.get(".copy-photo", "")) <= link


def test_a_row_being_pressed_fills_on_both_screens():
    """The phone's own highlight lit only the title. The app draws a pressed
    row instead, the same on the want list and a book's page, and only when
    the row's own link is pressed, not one of its controls."""
    rules = css_rules()

    for row, link in ((".book-row", ".book-row-title"), (".copy-row", ".copy-listing")):
        assert "-webkit-tap-highlight-color: transparent" in rules[row]
        for pressed in (f"{row}:has({link}:active)", f"{row}.pressed"):
            assert "background: var(--surface)" in rules[pressed], pressed


def test_the_app_presses_a_row_from_the_touch_itself():
    """A copy's tap hands the listing to the eBay app before the browser's
    own pressed state was seen on the phone (S73, #190). ui.js presses the
    row when a finger lands on its link, on either screen, and holds it long
    enough to see."""
    script = (
        Path(__file__).parent.parent / "src/book_watch/web/static/ui.js"
    ).read_text()

    assert '"pointerdown"' in script
    assert '.closest(".book-row-title, .copy-listing")' in script
    assert 'classList.add("pressed")' in script
    assert re.search(r"PRESS_MS = \d+", script)


def test_a_copy_row_gets_the_focus_ring_its_link_would():
    rules = css_rules()

    assert (
        "outline: 2px solid var(--accent)"
        in rules[".copy-row:has(.copy-listing:focus-visible)"]
    )

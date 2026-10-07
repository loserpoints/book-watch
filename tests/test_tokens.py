"""The design tokens: defined once, used everywhere, readable in both themes.

With no build step there is no utility framework holding the
line on colors and sizes, so these tests do it instead.
"""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch.web import assets, design, tokens

WEB = Path(tokens.__file__).parent
STYLESHEET = WEB / "static" / "app.css"
TEMPLATES = sorted((WEB / "templates").glob("*.html"))

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FUNCTION_COLOR = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklch|oklab)\(")
#: A length written as a number. Zero is not one: it is zero in any unit, and
#: `env(safe-area-inset-bottom, 0px)` needs it as a fallback.
RAW_LENGTH = re.compile(
    r"(?<![\w.-])(?!0+(?:\.0+)?(?:px|rem|em|pt)\b)\d*\.?\d+(?:px|rem|em|pt)\b"
)

#: Properties whose values must come from a token. Widths, heights and
#: borders are layout, and stay where they are used.
TOKENIZED = re.compile(
    r"^(?:color|background(?:-color)?|border(?:-\w+)?-color|font-size|font-family"
    r"|margin(?:-\w+)?|padding(?:-\w+)?|gap|row-gap|column-gap|border(?:-\w+)*-radius)$"
)


def declarations(css: str):
    """(property, value) for every declaration outside @font-face blocks."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@font-face\s*\{[^}]*\}", "", css)
    for prop, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+);", css):
        yield prop.strip().lower(), value.strip()


def violations(css: str):
    found = []
    for prop, value in declarations(css):
        if prop.startswith("--"):
            continue
        color = HEX.search(value) or FUNCTION_COLOR.search(value)
        length = TOKENIZED.match(prop) and RAW_LENGTH.search(value)
        if color or length:
            found.append(f"{prop}: {value}")
    return found


# --- the tokens themselves --------------------------------------------------


def test_every_color_has_a_dark_and_a_light_value():
    for name, entry in tokens.load()["color"].items():
        assert HEX.fullmatch(entry["dark"]), name
        assert HEX.fullmatch(entry["light"]), name


def test_every_token_reaches_the_css():
    css = tokens.css()
    data = tokens.load()
    for name in data["color"]:
        assert css.count(f"--{name}:") == 2, name  # once per theme
    for group, prefix in (
        ("font", "font"),
        ("text", "text"),
        ("space", "space"),
        ("radius", "radius"),
    ):
        for name in data[group]:
            assert f"--{prefix}-{name}:" in css


def test_dark_is_the_default_and_light_is_what_the_phone_asks_for():
    css = tokens.css()
    assert css.index(tokens.color("bg", "dark")) < css.index(
        "prefers-color-scheme: light"
    )
    assert css.index(tokens.color("bg", "light")) > css.index(
        "prefers-color-scheme: light"
    )


# --- readable in both themes --------------------------------------------------

#: Text that sits on each surface. AA for body text is 4.5.
TEXT_ON = {
    "bg": ["fg", "muted", "accent", "under", "over"],
    "surface": ["fg", "muted", "accent", "under", "over"],
    "accent": ["on-accent"],
    "placeholder-bg": ["placeholder-fg"],
}


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_text_meets_aa_contrast(theme):
    failures = []
    for surface, texts in TEXT_ON.items():
        for text in texts:
            ratio = tokens.contrast(
                tokens.color(text, theme), tokens.color(surface, theme)
            )
            if ratio < 4.5:
                failures.append(f"{text} on {surface}: {ratio:.2f}")
    assert failures == []


def test_contrast_is_computed_the_wcag_way():
    assert tokens.contrast("#000000", "#ffffff") == pytest.approx(21)
    assert tokens.contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


# --- nothing written outside the tokens ---------------------------------------


def test_the_stylesheet_uses_only_tokens():
    assert violations(STYLESHEET.read_text()) == []


def test_the_check_catches_what_it_is_for():
    """A rule that never fires proves nothing, so it is shown firing."""
    assert violations(".a { color: #ff0000; }")
    assert violations(".a { background: rgb(0 0 0); }")
    assert violations(".a { padding: 0.35rem; }")
    assert violations(".a { font-size: 13px; }")
    assert violations(".a { border-radius: 3px; }")
    assert not violations(".a { width: 72px; border: 1px solid var(--line); }")
    assert not violations(".a { padding: var(--space-2) 0; }")
    assert not violations(".a { padding: calc(var(--space-5) + env(x, 0px)); }")
    assert violations(".a { padding: calc(var(--space-5) + 0.5px); }")


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_templates_write_no_raw_colors_or_sizes(template):
    html = template.read_text()
    inline = " ".join(re.findall(r'style="([^"]*)"', html))
    blocks = " ".join(re.findall(r"<style>(.*?)</style>", html, flags=re.S))
    assert violations(f".inline {{ {inline}; }} {blocks}") == []


# --- how it reaches the page --------------------------------------------------


def test_the_stylesheet_url_changes_when_its_contents_do():
    url = assets.static_url("app.css")
    assert re.fullmatch(r"/static/app\.css\?v=[0-9a-f]{10}", url)


def test_the_design_page_shows_every_token():
    app = FastAPI()
    app.include_router(design.build_router())
    page = TestClient(app).get("/design")

    assert page.status_code == 200
    for name in tokens.load()["color"]:
        assert f"--{name}" in page.text
    for name in tokens.load()["space"]:
        assert f"--space-{name}" in page.text
    assert assets.static_url("app.css") in page.text
    assert tokens.color("bg", "dark") in page.text


def test_the_tokens_reach_the_page_unescaped():
    """Escaped quotes in a <style> block are not decoded, so an escaped token
    block silently loses every typeface. The first draft of S28 did exactly
    that, and only a screenshot showed it."""
    app = FastAPI()
    app.include_router(design.build_router())
    page = TestClient(app).get("/design").text

    head = page.split("</style>")[0]
    assert '"IBM Plex Sans"' in head
    assert "&#34;" not in head


# --- the display pieces (S29) -------------------------------------------------


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_nothing_is_hidden_behind_a_hover(template):
    """A phone has no hover, so a `title` that carries information hides it
    from the device this app is designed for first (principle 5)."""
    assert re.findall(r"\btitle=", template.read_text()) == []


def test_every_icon_button_is_a_44px_target():
    """Small to look at, big enough to hit."""
    rule = re.search(r"\.icon-btn\s*\{([^}]*)\}", STYLESHEET.read_text()).group(1)
    assert "width: 44px" in rule
    assert "height: 44px" in rule


def test_the_design_page_draws_every_row_state():
    app = FastAPI()
    app.include_router(design.build_router())
    page = TestClient(app).get("/design").text

    for sample in design.sample_books():
        assert sample["title"].replace("'", "&#39;") in page
    for words in (
        "Checking…",
        "Couldn't check just now",
        "Not checked yet",
        "2 maybes",
        "0 listed",
        "can&#39;t place",
        "only listing",
        "On your list",
        "(over your limit)",
    ):
        assert words in page, words

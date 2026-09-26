"""The design tokens, read from `tokens.toml` and handed to whoever needs them.

Two readers, deliberately. The web pages get CSS custom properties from
`css()`. The email, when *Tell me* builds it, gets plain values from
`colour()` and friends, because email clients ignore custom properties and
want every style inlined (decision 2, as revisited). One file feeds both, so
the email is built inside the system rather than restyled to look like it.
"""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path
from typing import Any, Literal

TOKENS_PATH = Path(__file__).parent / "tokens.toml"

Theme = Literal["dark", "light"]

#: Dark is the theme tuned first, so it is the default and light is the
#: exception a phone asks for (principle 8 in `docs/design.md`).
DEFAULT_THEME: Theme = "dark"


@cache
def load() -> dict[str, Any]:
    """The whole file, read once: it changes with a deploy, not a request."""
    with TOKENS_PATH.open("rb") as handle:
        return tomllib.load(handle)


def colour(name: str, theme: Theme = DEFAULT_THEME) -> str:
    """One colour's value in one theme, as a hex string."""
    return load()["colour"][name][theme]


def colours(theme: Theme = DEFAULT_THEME) -> dict[str, str]:
    return {name: entry[theme] for name, entry in load()["colour"].items()}


@cache
def css() -> str:
    """The tokens as CSS custom properties, dark first.

    Everything but colour is theme-free, so it is declared once. Colours are
    declared for dark on `:root`, and redeclared for light only when the phone
    asks for light. `color-scheme` follows, so native controls and scrollbars
    match the page.
    """
    tokens = load()
    shared = [
        *(f"--font-{name}: {value};" for name, value in tokens["font"].items()),
        *(f"--text-{name}: {value};" for name, value in tokens["text"].items()),
        *(f"--space-{name}: {value};" for name, value in tokens["space"].items()),
        *(f"--radius-{name}: {value};" for name, value in tokens["radius"].items()),
    ]
    dark = [f"--{name}: {value};" for name, value in colours("dark").items()]
    light = [f"--{name}: {value};" for name, value in colours("light").items()]
    return (
        ":root {\n  color-scheme: dark;\n  "
        + "\n  ".join(dark + shared)
        + "\n}\n@media (prefers-color-scheme: light) {\n  :root {\n"
        + "    color-scheme: light;\n    "
        + "\n    ".join(light)
        + "\n  }\n}\n"
    )


def contrast(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two hex colours, from 1 to 21.

    AA asks for 4.5 for body text and 3 for large text and non-text marks.
    Used by the tests, and shown on `/design` beside each colour.
    """

    def luminance(hex_colour: str) -> float:
        channels = [int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)

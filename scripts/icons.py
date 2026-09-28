"""Render the app's icons from their SVG sources (S35, #99).

    uv run --with playwright python scripts/icons.py

Run in a cloud session, which has Chromium installed, or anywhere Playwright
can find a browser. Nothing here runs on deploy: the PNGs are committed, and
this is only for when the SVGs change.

The sources name Courier Prime, which the app self-hosts; the page below
loads that file so the PNGs match the app's own titles rather than whatever
monospace the machine rendering them happens to have. It is embedded in the
page rather than linked: a page set from a string cannot read a local file,
and the first render silently fell back to a generic serif.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

STATIC = (
    Path(__file__).resolve().parent.parent / "src" / "book_watch" / "web" / "static"
)
ICONS = STATIC / "icons"
FONT = STATIC / "fonts" / "courier-prime-latin-700-normal.woff2"

#: Output name, source, size. Android asks for 192 and 512, and a maskable
#: 512 for its launcher shapes; iOS uses a 180 touch icon, square and uncropped.
RENDERS = [
    ("icon-192.png", "icon.svg", 192),
    ("icon-512.png", "icon.svg", 512),
    ("icon-maskable-512.png", "icon-maskable.svg", 512),
    ("apple-touch-icon.png", "icon.svg", 180),
]

#: The cloud sessions' Chromium, when Playwright's own download is absent.
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main() -> None:
    launch = {"executable_path": CHROMIUM} if os.path.exists(CHROMIUM) else {}
    font = base64.b64encode(FONT.read_bytes()).decode()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch)
        for name, source, size in RENDERS:
            page = browser.new_page(viewport={"width": size, "height": size})
            svg = (ICONS / source).read_text()
            page.set_content(
                "<style>"
                "@font-face { font-family: 'Courier Prime'; font-weight: 700;"
                f" src: url(data:font/woff2;base64,{font}) format('woff2'); }}"
                "html, body { margin: 0; }"
                f"svg {{ width: {size}px; height: {size}px; display: block; }}"
                f"</style>{svg}"
            )
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(ICONS / name))
            page.close()
            print(f"{name}: {size}x{size}")
        browser.close()


if __name__ == "__main__":
    main()

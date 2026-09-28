"""bookwatch installs like an app from the home screen (S35, #99).

What can be checked without a phone: the manifest is served and says what
Android needs, its colours are the tokens, every icon it names exists at the
size it claims, and no service worker is registered anywhere. That the phone
then opens it full screen is Alan's check, noted in the PR.
"""

import re
import struct
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch.web import manifest, tokens
from book_watch.web.app import STATIC_DIR

WEB = Path(manifest.__file__).parent


def served():
    app = FastAPI()
    app.include_router(manifest.build_router())
    return TestClient(app).get("/manifest.webmanifest")


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", header[16:24])


def test_the_manifest_says_what_an_installed_app_needs():
    response = served()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    body = response.json()
    assert body["name"] == body["short_name"] == "bookwatch"
    assert body["display"] == "standalone"
    assert body["start_url"] == "/"


def test_the_app_serves_it():
    """Through the real app, not only the router on its own."""
    from book_watch.config import DeletionEndpointConfig
    from book_watch.web.app import create_app

    config = DeletionEndpointConfig(
        verification_token="a" * 32,
        endpoint_url="https://book-watch.fly.dev/ebay/deletion",
    )
    client = TestClient(create_app(config))

    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/static/icons/icon-512.png").status_code == 200


def test_its_colours_are_the_tokens():
    """So the splash and status bar cannot drift from the app."""
    body = served().json()

    assert body["background_color"] == tokens.colour("bg")
    assert body["theme_color"] == tokens.colour("bg")


def test_every_icon_exists_at_the_size_it_claims():
    icons = served().json()["icons"]

    for icon in icons:
        path = STATIC_DIR / icon["src"].removeprefix("/static/")
        width, height = (int(n) for n in icon["sizes"].split("x"))
        assert png_size(path) == (width, height), icon["src"]
    # Android asks for both sizes, and a maskable one for its launcher shapes.
    assert {icon["sizes"] for icon in icons} >= {"192x192", "512x512"}
    assert any(icon.get("purpose") == "maskable" for icon in icons)


def test_every_page_links_the_manifest_and_its_icons():
    base = (WEB / "templates" / "base.html").read_text()

    assert '<link rel="manifest" href="/manifest.webmanifest">' in base
    for href in re.findall(
        r'<link rel="(?:icon|apple-touch-icon)" href="([^"]+)"', base
    ):
        assert (STATIC_DIR / href.removeprefix("/static/")).exists(), href


def test_no_service_worker_is_registered():
    """A worker that caches pages would serve yesterday's copies
    as today's."""
    for path in [*WEB.rglob("*.html"), *WEB.rglob("*.js"), *WEB.rglob("*.py")]:
        if path.name.endswith(".min.js"):
            continue  # htmx, vendored; it mentions nothing of the kind anyway
        assert "serviceWorker" not in path.read_text(), path

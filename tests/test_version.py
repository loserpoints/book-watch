"""Coming back to the app after a deploy reloads it fresh (S75, #256).

What can be checked without a browser: every page says which version drew
it, the server answers which version is running and never lets that answer
be cached, and the version changes with the code and nothing else. That the
page reloads on coming back is checked in Chromium and then on the phone.
"""

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from book_watch.web import assets, design, version


def client() -> TestClient:
    app = FastAPI()
    app.include_router(design.build_router())
    app.include_router(version.build_router())
    return TestClient(app)


def test_a_page_carries_the_version_the_server_reports():
    page = client().get("/design").text
    running = client().get("/version")

    drawn_by = re.search(r'<meta name="app-version" content="([0-9a-f]+)">', page)
    assert drawn_by, "the page doesn't say which version drew it"
    assert running.text == drawn_by.group(1) == assets.app_version()


def test_the_running_version_is_never_cached():
    assert client().get("/version").headers["cache-control"] == "no-store"


def test_the_version_changes_with_the_code_and_nothing_else(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.css").write_text("p { color: red }")
    (tmp_path / "app.py").write_text("x = 1")
    before = assets.fingerprint(tmp_path)

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\0")
    (tmp_path / "web" / "stray.pyc").write_bytes(b"\0")
    assert assets.fingerprint(tmp_path) == before

    (tmp_path / "web" / "app.css").write_text("p { color: blue }")
    assert assets.fingerprint(tmp_path) != before

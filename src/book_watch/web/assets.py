"""What every template needs to find the stylesheet and the tokens.

Static files are served under a version tag taken from their contents, so a
phone caches `app.css` until it actually changes and never shows yesterday's
styles against today's markup. The tag is computed once, at startup: a file
under `static/` changes with a deploy, never while the app is running.

This is not a build step (decision 2). Nothing is compiled or rewritten; the
file served is the file in the repository.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from book_watch.web import tokens

STATIC_DIR = Path(__file__).parent / "static"


@cache
def version(name: str) -> str:
    """A short fingerprint of a static file's contents."""
    return hashlib.sha256((STATIC_DIR / name).read_bytes()).hexdigest()[:10]


def static_url(name: str) -> str:
    return f"/static/{name}?v={version(name)}"


def register(env: Environment) -> None:
    """Give a template environment the stylesheet link and the tokens."""
    env.globals["static_url"] = static_url
    # Marked safe because it is ours, generated from `tokens.toml`, and because
    # escaping it breaks it: autoescape turns the quotes around "IBM Plex Sans"
    # into &#34;, which inside <style> is not decoded, so every font silently
    # fell back to the browser default. A test asserts the quotes survive.
    env.globals["tokens_css"] = Markup(tokens.css())
    # The browser's own chrome (the address bar on Android) in the page colour.
    env.globals["theme_colour"] = tokens.colour("bg")

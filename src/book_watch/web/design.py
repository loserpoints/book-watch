"""`/design`: every token, drawn, so the system can be checked on a phone.

Public, and deliberately so for now: the app has no login, so nothing here is
more exposed than the rest of it, and the page shows no books of Alan's, only
the tokens. If book-watch ever has other users, this moves behind an admin
area (S28, #96).

It also draws every display piece in every state (S29, #97), from the
sample values below, never from the database. A state that exists in the data
and not here is a state nobody has designed.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch.web import assets, strips, tokens

TEMPLATES_DIR = Path(__file__).parent / "templates"


#: Sample books and copies. Invented, and plausible on purpose: every state a
#: row can be in, with prices that make the strips worth reading.
SEEN = [10.49, 12, 14.5, 27]
LONG_SEEN = [6.5, 7.99, 8.5, 9, 9.25, 11, 12, 12.5, 14, 19]


def sample_books() -> list[dict]:
    base = {"href": "#", "cover_url": None}
    return [
        {
            **base,
            "title": "Crash",
            "author": "J. G. Ballard",
            "state": "ok",
            "listed": 3,
            "new": 2,
            "checked": "4m",
            "added": "3w",
            "price_text": "$10.49",
            "verdict": "under",
            "strip": strips.range_strip(SEEN, 12),
        },
        {
            **base,
            "title": "Breaking and Entering",
            "author": "Joy Williams",
            "state": "ok",
            "listed": 9,
            "checked": "2h",
            "added": "2d",
            "examining": "digging",
            "price_text": "$18",
            "verdict": "over",
            "over_by": "$3",
            "strip": strips.range_strip([18, 19.5, 21, 22, 24, 26, 29, 31, 36], 15),
        },
        {
            **base,
            "title": "State of Grace",
            "author": "Joy Williams",
            "state": "ok",
            "listed": 5,
            "checked": "1d",
            "added": "4mo",
            "examining": "throttled",
            "price_text": "$21",
            "verdict": None,
            "strip": strips.range_strip([21, 23, 25, 30, 36]),
        },
        {
            **base,
            "title": "A Heartbreaking Work of Staggering Genius",
            "author": "Dave Eggers",
            "state": "ok",
            "listed": 14,
            "checked": "12m",
            "added": "just now",
            "price_text": "$7.99",
            "verdict": "under",
            "strip": strips.range_strip(LONG_SEEN, 10),
        },
        {
            **base,
            "title": "Stoner",
            "author": "John Williams",
            "state": "maybes",
            "maybes": 2,
            "checked": "just now",
            "added": "5d",
        },
        {
            **base,
            "title": "The Quick and the Dead",
            "author": "Joy Williams",
            "state": "checking",
            "added": "just now",
        },
        {
            **base,
            "title": "Taking Care",
            "author": "Joy Williams",
            "state": "failed",
            "added": "1w",
        },
        {
            **base,
            "title": "Honored Guest",
            "author": "Joy Williams",
            "state": "unchecked",
            "added": "3mo",
        },
        {
            **base,
            "title": "The Visiting Privilege",
            "author": "Joy Williams",
            "state": "none",
            "checked": "3h",
            "added": "6d",
        },
    ]


def sample_copies() -> list[dict]:
    used = [10.49, 12.0, 27.0]
    common = {
        "url": "#",
        "photo_url": SAMPLE_PHOTO,
        "seller": "betterworldbooks",
        "edition": "Paperback · Vintage · 1995",
        "abroad": None,
        "note": None,
    }
    return [
        {
            **common,
            "price_text": "$10.49",
            "verdict": "under",
            "place": strips.rank_strip(used, 10.49),
            "condition": "Good",
            "new": True,
            "listing_title": (
                "Crash by J. G. Ballard (1995, Vintage paperback) good reading copy"
            ),
            "note": "Light shelf wear. Pages clean, no markings.",
        },
        {
            **common,
            "price_text": "$12",
            "verdict": "under",
            "place": strips.rank_strip(used, 12.0),
            "condition": "Very Good",
            "abroad": "GB",
            "seller": "thriftbooks",
            "listing_title": "CRASH J.G. Ballard Vintage International PB very good",
        },
        {
            **common,
            "price_text": "$27",
            "verdict": "over",
            "over_by": "$15",
            "place": strips.rank_strip(used, 27.0),
            "condition": "Good",
            "seller": "oldpaperbacks",
            "listing_title": "Crash - J G Ballard - Vintage 1995 - ex-library, stamps",
            "note": "Ex-library with stamps and card pocket. No dust jacket.",
            "photos": SAMPLE_PHOTOS,
        },
        {
            **common,
            "price_text": "$19",
            "verdict": "over",
            "over_by": "$7",
            "place_text": "only new listing",
            "condition": "Brand New",
            "seller": "bookdepot",
            "listing_title": "Crash: A Novel by J. G. Ballard, New Paperback",
        },
        {
            **common,
            "price_text": "$7.50",
            "verdict": "unknown",
            "place_text": "can't place: shipping unknown",
            "condition": "Acceptable",
            "seller": "goodwill_books",
            "listing_title": "Crash Ballard paperback",
            "note": (
                "Reading copy only. Some highlighting and pencil notes in the "
                "first three chapters, a coffee ring on the back cover, and the "
                "spine is creased from reading. Binding is tight and all pages are "
                "present. We ship within one business day in a padded mailer. "
                "Please see all photos and ask any questions before purchasing."
            ),
        },
    ]


#: A stand-in seller's photo: sample content, not interface, so it carries its
#: own colours. A real one is an eBay image URL, which `photos.larger` enlarges.
def _sample_photo(label: str) -> str:
    return (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' width='225' height='300'>"
        "<rect width='225' height='300' fill='%23443a2e'/>"
        "<rect x='45' y='40' width='135' height='210' rx='4' fill='%236b563f'/>"
        "<text x='112' y='150' font-family='serif' font-size='22' fill='%23f1e6d2' "
        f"text-anchor='middle'>{label}</text></svg>"
    )


SAMPLE_PHOTO = _sample_photo("CRASH")

#: A copy with several photos, as `getItem` returns them since S33: the main
#: one first. Tapping it shows all three.
SAMPLE_PHOTOS = [SAMPLE_PHOTO, _sample_photo("STAMPS"), _sample_photo("SPINE")]


def sample_candidates() -> list[dict]:
    return [
        {
            "title": "Stoner",
            "author": "John Williams",
            "year": 1965,
            "editions": 49,
            "cover_url": None,
            "on_list": True,
        },
        {
            "title": "Stoner",
            "author": "John Williams",
            "year": 2003,
            "editions": 3,
            "cover_url": None,
        },
        {
            "title": "Stoner and Butcher's Crossing",
            "author": None,
            "year": 2012,
            "editions": 1,
            "cover_url": None,
        },
    ]


def build_router() -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    assets.register(templates.env)

    @router.get("/design", response_class=HTMLResponse)
    def design(request: Request) -> HTMLResponse:
        data = tokens.load()
        colours = [
            {
                "name": name,
                "use": entry.get("use", ""),
                "dark": entry["dark"],
                "light": entry["light"],
                "dark_contrast": tokens.contrast(
                    entry["dark"], tokens.colour("bg", "dark")
                ),
                "light_contrast": tokens.contrast(
                    entry["light"], tokens.colour("bg", "light")
                ),
            }
            for name, entry in data["colour"].items()
        ]
        return templates.TemplateResponse(
            request,
            "design.html",
            {
                "colours": colours,
                "text": data["text"],
                "space": data["space"],
                "radius": data["radius"],
                "fonts": data["font"],
                "books": sample_books(),
                "copies": sample_copies(),
                "candidates": sample_candidates(),
                "market_strip": strips.range_strip(SEEN, 12, width=320, height=20),
            },
        )

    return router

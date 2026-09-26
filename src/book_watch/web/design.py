"""`/design`: every token, drawn, so the system can be checked on a phone.

Public, and deliberately so for now: the app has no login, so nothing here is
more exposed than the rest of it, and the page shows no books of Alan's, only
the tokens. If book-watch ever has other users, this moves behind an admin
area (S28, #96).

From S29 it also shows every primitive in every state.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from book_watch.web import assets, tokens

TEMPLATES_DIR = Path(__file__).parent / "templates"


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
            },
        )

    return router

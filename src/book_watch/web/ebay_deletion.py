"""eBay's marketplace account deletion endpoint.

eBay requires every production application either to receive account-deletion
notifications or to be granted an exemption, and restricts the keyset until one
of those is true. This is the receiving half. See docs/decisions.md entry 16.

Two jobs:

* **GET** — eBay's endpoint validation. It sends a challenge code; the correct
  answer proves we hold the verification token, which proves the endpoint is
  ours. eBay calls this when the endpoint is saved and re-checks it later, so
  it has to keep working, not just work once.
* **POST** — an eBay user closed their account, and anything held about them
  must be deleted.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from book_watch.config import DeletionEndpointConfig, load_deletion_config

logger = logging.getLogger(__name__)

DELETION_PATH = "/ebay/deletion"


def challenge_response(
    challenge_code: str, *, verification_token: str, endpoint_url: str
) -> str:
    """Hash the three values eBay expects, in the order eBay expects them.

    The endpoint URL is part of the hash, which is what stops a valid response
    being replayed against a different endpoint. It must be the URL configured
    in eBay's console rather than the one the request arrived at — behind a
    proxy those differ, and eBay compares against its own copy.
    """
    digest = hashlib.sha256()
    digest.update(challenge_code.encode("utf-8"))
    digest.update(verification_token.encode("utf-8"))
    digest.update(endpoint_url.encode("utf-8"))
    return digest.hexdigest()


def build_router(config: DeletionEndpointConfig) -> APIRouter:
    router = APIRouter()

    @router.get(DELETION_PATH)
    def validate_endpoint(challenge_code: str) -> JSONResponse:
        return JSONResponse(
            {
                "challengeResponse": challenge_response(
                    challenge_code,
                    verification_token=config.verification_token,
                    endpoint_url=config.endpoint_url,
                )
            }
        )

    @router.post(DELETION_PATH, status_code=200)
    def receive_notification(payload: dict[str, Any]) -> dict[str, str]:
        # Acknowledged and nothing deleted, because nothing is stored: this
        # application keeps listings, not the people who posted them. If that
        # ever changes, the deletion has to happen here — and the signature
        # check deferred in decisions.md entry 17 has to land first.
        #
        # The payload is deliberately not logged. It identifies the very user
        # whose data eBay is asking us to erase, and a log line is storage.
        logger.info("Received an eBay account deletion notification.")
        return {"status": "acknowledged"}

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return router


def create_app(config: DeletionEndpointConfig | None = None) -> FastAPI:
    """Build the application.

    Configuration is injected so tests never depend on the environment, and
    loaded from it when nothing is passed. Loading eagerly means a missing or
    malformed token fails at startup with a clear message rather than at the
    moment eBay validates the endpoint.
    """
    app = FastAPI(
        title="book-watch",
        description="Personal used-book want-list watcher.",
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(build_router(config or load_deletion_config()))
    return app

"""Credentials and settings, read from the environment.

Nothing secret is ever read from a file that git tracks. In development the
values come from a gitignored `.env`; in production they come from the
platform's own secret store. `.env.example` documents the names and holds no
values. See docs/decisions.md entry 11.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class MissingCredentialError(RuntimeError):
    """A required environment variable is unset or empty."""


@dataclass(frozen=True, slots=True, repr=False)
class EbayCredentials:
    """An eBay application's client ID and secret.

    The default dataclass repr is suppressed. These objects end up in
    tracebacks and log lines, and a secret printed there is a secret that has
    to be rotated.
    """

    client_id: str
    client_secret: str

    def __repr__(self) -> str:
        return "EbayCredentials(client_id=<hidden>, client_secret=<hidden>)"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingCredentialError(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            f"or export {name} in your shell."
        )
    return value


def load_ebay_credentials(*, use_dotenv: bool = True) -> EbayCredentials:
    """Read the eBay keys from the environment.

    `load_dotenv` does not overwrite variables that are already set, so a real
    environment variable always beats the `.env` file. Tests pass
    `use_dotenv=False` so a developer's own `.env` cannot influence them.
    """
    if use_dotenv:
        load_dotenv()
    return EbayCredentials(
        client_id=_require("EBAY_CLIENT_ID"),
        client_secret=_require("EBAY_CLIENT_SECRET"),
    )

"""Credentials and settings, read from the environment.

Nothing secret is ever read from a file that git tracks. In development the
values come from a gitignored `.env`; in production they come from the
platform's own secret store. `.env.example` documents the names and holds no
values. See docs/decisions.md entry 11.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

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


#: eBay requires the verification token to be 32-80 characters of
#: alphanumerics, underscores and hyphens. Checking it here turns a confusing
#: rejection in eBay's console into a clear error before anything is deployed.
_VERIFICATION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,80}$")


class InvalidConfigError(RuntimeError):
    """A setting is present but cannot be used."""


@dataclass(frozen=True, slots=True, repr=False)
class DeletionEndpointConfig:
    """Settings for the eBay marketplace account deletion endpoint.

    `endpoint_url` is the URL as typed into eBay's developer console, not
    whatever URL a request happens to arrive at. It is one of the three inputs
    to the challenge hash, so it has to match eBay's copy exactly — a
    difference of one trailing slash produces a valid-looking hash that eBay
    rejects.
    """

    verification_token: str
    endpoint_url: str

    def __repr__(self) -> str:
        return (
            f"DeletionEndpointConfig(verification_token=<hidden>, "
            f"endpoint_url={self.endpoint_url!r})"
        )


def load_deletion_config(*, use_dotenv: bool = True) -> DeletionEndpointConfig:
    """Read the deletion-endpoint settings from the environment."""
    if use_dotenv:
        load_dotenv()

    token = _require("EBAY_VERIFICATION_TOKEN")
    if not _VERIFICATION_TOKEN_PATTERN.match(token):
        raise InvalidConfigError(
            "EBAY_VERIFICATION_TOKEN must be 32-80 characters of letters, "
            f"digits, underscores and hyphens; got {len(token)} characters. "
            "eBay will reject anything else."
        )

    url = _require("EBAY_DELETION_ENDPOINT_URL")
    if not url.startswith("https://"):
        raise InvalidConfigError(
            f"EBAY_DELETION_ENDPOINT_URL must be an https:// URL; got {url!r}. "
            "eBay will not call a plaintext endpoint."
        )

    return DeletionEndpointConfig(verification_token=token, endpoint_url=url)


def load_database_path(*, use_dotenv: bool = True) -> Path:
    """Where the SQLite file lives.

    Required rather than defaulting to something in the working directory.
    A default would be friendlier locally and dangerous in production: an
    unset variable would write to the container's own filesystem, the app
    would look perfectly healthy, and the want-list would vanish on the next
    deploy. A missing variable that stops the process is the loud version of
    the same mistake.
    """
    if use_dotenv:
        load_dotenv()
    return Path(_require("BOOK_WATCH_DB_PATH"))

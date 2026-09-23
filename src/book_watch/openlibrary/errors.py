"""Exceptions raised by the Open Library client."""

from __future__ import annotations


class OpenLibraryError(Exception):
    """Anything that went wrong talking to Open Library."""


class OpenLibraryUnavailable(OpenLibraryError):
    """Open Library could not be reached, or answered with something unusable.

    Deliberately *not* raised when Open Library answers clearly that it has no
    record of something. That is a fact about the catalogue and comes back as
    `None`; this is an absence of information about the catalogue.

    Decision 33 makes the difference load-bearing. A number Open Library does
    not hold must not exclude a listing — all five such numbers in the
    measured sample were non-English editions of the right book. A number we
    *failed to ask about* must not silently do the same thing, or an outage
    would quietly downgrade every listing and look like normal operation.
    """

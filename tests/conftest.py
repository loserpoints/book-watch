"""Shared test setup.

The one thing here exists because of a near miss: a router gained an Open
Library client with a real default, the want-list tests did not pass a stub,
and the suite quietly started making live requests to a non-profit on every
run. Nothing failed. It was visible only as the suite taking four times as
long.

Decision 7 calls low volume a constraint rather than a preference, and CI
running on every push is exactly the kind of volume that gets an address
blocked. So an accidental request is now a loud failure instead of a silent
one.
"""

import httpx
import pytest

from book_watch.openlibrary import forget_the_pace


@pytest.fixture(autouse=True)
def no_accidental_network(request, monkeypatch):
    """Refuse any real HTTP request from a test not marked `network`.

    Patched at the transport rather than at the client, so the two kinds of
    faking already in use still work: `httpx.MockTransport` and the test
    client's ASGI transport are different classes and never reach this. Only a
    transport that would really open a socket is stopped.
    """
    if "network" in request.keywords:
        return

    def refuse(self, outgoing, *args, **kwargs):
        raise AssertionError(
            f"This test tried to really call {outgoing.url}.\n"
            "Pass a stub or an httpx.MockTransport. If the test is meant to "
            "make a real request, mark it @pytest.mark.network."
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


@pytest.fixture(autouse=True)
def a_fresh_pace():
    """Forget when Open Library was last spoken to, between tests.

    The pacing is process-wide on purpose — the limit is per address, not per
    client object — which means it is also test-wide unless something clears
    it. Without this, a test that faked the clock would leave a timestamp for
    the next one to wait behind.
    """
    forget_the_pace()
    yield
    forget_the_pace()

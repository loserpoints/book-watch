"""Tests for eBay's account-deletion endpoint.

The hash is the whole point of this endpoint, and getting it wrong is the
difference between a compliant keyset and a disabled one, so it is checked
against an independently computed value rather than against the function's own
output.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from book_watch.config import DeletionEndpointConfig
from book_watch.web.ebay_deletion import DELETION_PATH, challenge_response, create_app

TOKEN = "a" * 32
ENDPOINT = "https://book-watch.fly.dev/ebay/deletion"
CONFIG = DeletionEndpointConfig(verification_token=TOKEN, endpoint_url=ENDPOINT)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(CONFIG))


def test_the_hash_is_code_then_token_then_url():
    expected = hashlib.sha256(f"abc123{TOKEN}{ENDPOINT}".encode()).hexdigest()

    assert (
        challenge_response("abc123", verification_token=TOKEN, endpoint_url=ENDPOINT)
        == expected
    )


def test_the_url_is_part_of_the_hash():
    # A response valid for one endpoint must not be valid for another, and a
    # stray trailing slash must not go unnoticed.
    ours = challenge_response("abc", verification_token=TOKEN, endpoint_url=ENDPOINT)
    theirs = challenge_response(
        "abc", verification_token=TOKEN, endpoint_url=ENDPOINT + "/"
    )

    assert ours != theirs


def test_a_different_challenge_gives_a_different_answer():
    first = challenge_response("abc", verification_token=TOKEN, endpoint_url=ENDPOINT)
    second = challenge_response("xyz", verification_token=TOKEN, endpoint_url=ENDPOINT)

    assert first != second


def test_the_endpoint_answers_ebays_challenge(client):
    response = client.get(DELETION_PATH, params={"challenge_code": "abc123"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "challengeResponse": hashlib.sha256(
            f"abc123{TOKEN}{ENDPOINT}".encode()
        ).hexdigest()
    }


def test_the_endpoint_never_echoes_the_token(client):
    response = client.get(DELETION_PATH, params={"challenge_code": "abc123"})

    assert TOKEN not in response.text


def test_a_challenge_without_a_code_is_rejected(client):
    assert client.get(DELETION_PATH).status_code == 422


def test_a_deletion_notification_is_acknowledged(client):
    payload = {
        "metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION"},
        "notification": {"data": {"username": "someone", "userId": "abc"}},
    }

    response = client.post(DELETION_PATH, json=payload)

    # eBay retries anything that is not a 2xx, and repeated failures put the
    # keyset back to non-compliant.
    assert response.status_code == 200


def test_a_deletion_notification_is_not_logged(client, caplog):
    payload = {"notification": {"data": {"username": "someone-identifiable"}}}

    with caplog.at_level("INFO"):
        client.post(DELETION_PATH, json=payload)

    assert "someone-identifiable" not in caplog.text


def test_health_is_available_for_flys_checks(client):
    assert client.get("/health").status_code == 200

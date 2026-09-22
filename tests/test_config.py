import pytest

from book_watch.config import (
    EbayCredentials,
    InvalidConfigError,
    MissingCredentialError,
    load_deletion_config,
    load_ebay_credentials,
)


def test_reads_both_keys_from_the_environment(monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", "an-app-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "a-cert-id")

    credentials = load_ebay_credentials(use_dotenv=False)

    assert credentials == EbayCredentials("an-app-id", "a-cert-id")


@pytest.mark.parametrize("missing", ["EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"])
def test_an_unset_key_names_itself(monkeypatch, missing):
    monkeypatch.setenv("EBAY_CLIENT_ID", "an-app-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "a-cert-id")
    monkeypatch.delenv(missing)

    with pytest.raises(MissingCredentialError, match=missing):
        load_ebay_credentials(use_dotenv=False)


def test_a_whitespace_only_key_counts_as_missing(monkeypatch):
    # The common way to get here is a `.env` line like `EBAY_CLIENT_ID= `,
    # which otherwise fails much later with a confusing 401.
    monkeypatch.setenv("EBAY_CLIENT_ID", "   ")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "a-cert-id")

    with pytest.raises(MissingCredentialError):
        load_ebay_credentials(use_dotenv=False)


def test_repr_hides_the_secret():
    credentials = EbayCredentials("an-app-id", "super-secret")

    assert "super-secret" not in repr(credentials)
    assert "an-app-id" not in repr(credentials)


def test_a_short_verification_token_is_rejected(monkeypatch):
    monkeypatch.setenv("EBAY_VERIFICATION_TOKEN", "too-short")
    monkeypatch.setenv("EBAY_DELETION_ENDPOINT_URL", "https://example.com/x")

    with pytest.raises(InvalidConfigError, match="32-80"):
        load_deletion_config(use_dotenv=False)


def test_a_verification_token_with_illegal_characters_is_rejected(monkeypatch):
    monkeypatch.setenv("EBAY_VERIFICATION_TOKEN", "!" * 40)
    monkeypatch.setenv("EBAY_DELETION_ENDPOINT_URL", "https://example.com/x")

    with pytest.raises(InvalidConfigError):
        load_deletion_config(use_dotenv=False)


def test_a_plaintext_endpoint_is_rejected(monkeypatch):
    monkeypatch.setenv("EBAY_VERIFICATION_TOKEN", "a" * 32)
    monkeypatch.setenv("EBAY_DELETION_ENDPOINT_URL", "http://example.com/x")

    with pytest.raises(InvalidConfigError, match="https"):
        load_deletion_config(use_dotenv=False)


def test_a_valid_deletion_config_loads(monkeypatch):
    monkeypatch.setenv("EBAY_VERIFICATION_TOKEN", "a" * 32)
    monkeypatch.setenv("EBAY_DELETION_ENDPOINT_URL", "https://example.com/x")

    config = load_deletion_config(use_dotenv=False)

    assert config.endpoint_url == "https://example.com/x"
    assert "a" * 32 not in repr(config)

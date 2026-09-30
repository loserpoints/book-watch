import pytest

from book_watch.config import (
    EbayCredentials,
    InvalidConfigError,
    MissingCredentialError,
    load_deletion_config,
    load_ebay_credentials,
    load_ship_to_zip,
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


def test_no_ship_to_zip_means_none(monkeypatch):
    monkeypatch.delenv("SHIP_TO_ZIP", raising=False)

    assert load_ship_to_zip(use_dotenv=False) is None


@pytest.mark.parametrize("zip_code", ["10001", "10001-1234"])
def test_a_ship_to_zip_loads(monkeypatch, zip_code):
    monkeypatch.setenv("SHIP_TO_ZIP", f" {zip_code} ")

    assert load_ship_to_zip(use_dotenv=False) == zip_code


def test_a_malformed_ship_to_zip_is_rejected_without_echoing_it(monkeypatch):
    monkeypatch.setenv("SHIP_TO_ZIP", "1000l")

    with pytest.raises(InvalidConfigError, match="SHIP_TO_ZIP") as caught:
        load_ship_to_zip(use_dotenv=False)
    assert "1000l" not in str(caught.value)

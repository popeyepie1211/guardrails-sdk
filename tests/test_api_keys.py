import pytest

from guardrail_ai.core.api_keys import generate_api_key, hash_api_key, verify_api_key


def test_api_key_hashing_and_verification(monkeypatch):
    monkeypatch.setenv("API_KEY_PEPPER", "unit-test-pepper")
    api_key = generate_api_key()
    stored_hash = hash_api_key(api_key)

    assert api_key.startswith("gr_")
    assert len(api_key) >= 40
    assert stored_hash.startswith("hmac-sha256$")
    assert api_key not in stored_hash
    assert verify_api_key(api_key, stored_hash)
    assert not verify_api_key(f"{api_key}wrong", stored_hash)


def test_hashing_fails_closed_without_pepper(monkeypatch):
    monkeypatch.delenv("API_KEY_PEPPER", raising=False)

    with pytest.raises(RuntimeError, match="API_KEY_PEPPER must be set"):
        hash_api_key("gr_test")

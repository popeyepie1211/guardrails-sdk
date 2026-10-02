"""API-key generation and one-way hashing for model telemetry authentication."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets


API_KEY_HASH_PREFIX = "hmac-sha256$"
API_KEY_PEPPER_ENV = "API_KEY_PEPPER"


def _get_pepper() -> bytes:
    """Return the required server-side pepper, failing closed if unset."""
    pepper = os.getenv(API_KEY_PEPPER_ENV)
    if not pepper:
        raise RuntimeError(
            f"{API_KEY_PEPPER_ENV} must be set before generating or hashing API keys."
        )
    return pepper.encode("utf-8")


def generate_api_key() -> str:
    """Generate a high-entropy API key suitable for returning once to a client."""
    return f"gr_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Return a versioned HMAC-SHA-256 hash; never persist ``api_key`` itself."""
    if not isinstance(api_key, str) or not api_key:
        raise ValueError("api_key must be a non-empty string.")

    digest = hmac.new(
        _get_pepper(),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{API_KEY_HASH_PREFIX}{digest}"


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify a key with a constant-time comparison (used by Python tests/tools)."""
    if not isinstance(api_key, str) or not api_key:
        return False
    if not isinstance(stored_hash, str) or not stored_hash.startswith(API_KEY_HASH_PREFIX):
        return False

    expected = hash_api_key(api_key)
    return hmac.compare_digest(expected, stored_hash)

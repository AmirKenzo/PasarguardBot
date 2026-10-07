"""Process secrets cache: getters fail loudly until the cache is seeded."""

from __future__ import annotations

import pytest

from app.utils.security.secrets_cache import (
    SECRET_CRYPTO_KEY,
    SECRET_WEBHOOK,
    _cache,
    generate_secret_value,
    get_crypto_key,
    get_webhook_secret,
)


@pytest.fixture(autouse=True)
def _reset_secrets_cache():
    _cache.clear()
    yield
    _cache.clear()


def test_getters_raise_when_cache_empty():
    with pytest.raises(RuntimeError, match="crypto_key"):
        get_crypto_key()
    with pytest.raises(RuntimeError, match="webhook_secret"):
        get_webhook_secret()


def test_getters_return_cached_values():
    _cache[SECRET_CRYPTO_KEY] = "crypto-test-value"
    _cache[SECRET_WEBHOOK] = "webhook-test-value"
    assert get_crypto_key() == "crypto-test-value"
    assert get_webhook_secret() == "webhook-test-value"


def test_generate_secret_value_non_empty():
    value = generate_secret_value()
    assert isinstance(value, str)
    assert value
    assert len(value) == 64

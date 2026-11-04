from __future__ import annotations

import pytest

from app.utils.security.crypto import DecryptionError, decrypt_data, encrypt_data
from app.utils.security.secrets_cache import SECRET_CRYPTO_KEY, _cache


@pytest.fixture(autouse=True)
def _crypto_key():
    saved = _cache.get(SECRET_CRYPTO_KEY)
    _cache[SECRET_CRYPTO_KEY] = "original-key"
    yield
    if saved is None:
        _cache.pop(SECRET_CRYPTO_KEY, None)
    else:
        _cache[SECRET_CRYPTO_KEY] = saved


def test_round_trip() -> None:
    assert decrypt_data(encrypt_data("p@ss-éü")) == "p@ss-éü"


def test_wrong_key_raises_decryption_error() -> None:
    # Long plaintext so wrong-key garbage is practically never valid UTF-8.
    encrypted = encrypt_data("panel-password-" * 8)
    _cache[SECRET_CRYPTO_KEY] = "another-key"

    with pytest.raises(DecryptionError, match="crypto_key") as exc_info:
        decrypt_data(encrypted)
    assert isinstance(exc_info.value, ValueError)


def test_invalid_base64_raises_decryption_error() -> None:
    with pytest.raises(DecryptionError):
        decrypt_data("not base64 !!")

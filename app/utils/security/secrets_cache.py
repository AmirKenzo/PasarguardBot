from __future__ import annotations

import secrets
from typing import Final

SECRET_CRYPTO_KEY = "crypto_key"
SECRET_WEBHOOK = "webhook_secret"
SECRET_NAMES: tuple[str, ...] = (SECRET_CRYPTO_KEY, SECRET_WEBHOOK)

_cache: dict[str, str] = {}
_RANDOM_BYTES: Final[int] = 32


def generate_secret_value() -> str:
    return secrets.token_hex(_RANDOM_BYTES)


def get_crypto_key() -> str:
    value = _cache.get(SECRET_CRYPTO_KEY)
    if not value:
        raise RuntimeError("crypto_key is not loaded; call ensure_secrets() at boot")
    return value


def get_webhook_secret() -> str:
    value = _cache.get(SECRET_WEBHOOK)
    if not value:
        raise RuntimeError("webhook_secret is not loaded; call ensure_secrets() at boot")
    return value

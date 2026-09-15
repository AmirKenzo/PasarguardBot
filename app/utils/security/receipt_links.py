"""Single-use, expiring tokens for streaming a transaction's receipt photo.

A plain <img> tag can't send the panel's normal session-token/init-data auth,
so viewing a receipt goes through a short-lived HMAC-signed link instead,
scoped to one transaction and one admin.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from app.utils.security.secrets_cache import get_crypto_key

LINK_TTL_SECONDS = 2 * 60

_signing_key: bytes | None = None
# nonce -> consumed_at
_consumed_nonces: dict[str, float] = {}
_PRUNE_INTERVAL_SECONDS = 60.0
_last_prune = 0.0


def _get_signing_key() -> bytes:
    global _signing_key
    if _signing_key is None:
        _signing_key = hashlib.sha256(get_crypto_key().encode("utf-8") + b"|receipt_links").digest()
    return _signing_key


def _prune(now: float | None = None) -> None:
    global _last_prune
    now = time.time() if now is None else now
    if now - _last_prune < _PRUNE_INTERVAL_SECONDS:
        return
    _last_prune = now
    for nonce, consumed_at in list(_consumed_nonces.items()):
        if now - consumed_at > LINK_TTL_SECONDS:
            _consumed_nonces.pop(nonce, None)


def create_receipt_token(admin_id: int, tx_id: int) -> str:
    """Mint a single-use HMAC-signed token for streaming one transaction's receipt."""
    _prune()
    nonce = secrets.token_urlsafe(12)
    exp = int(time.time()) + LINK_TTL_SECONDS
    body = f"{admin_id}.{tx_id}.{exp}.{nonce}"
    sig = hmac.new(_get_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def consume_receipt_token(token: str) -> tuple[bool, str | None, int | None, int | None]:
    """Validate and atomically consume a receipt token.

    Returns ``(ok, error_message, admin_id, tx_id)``. A token can only ever be
    consumed once, regardless of whether it has expired yet.
    """
    _prune()
    parts = (token or "").split(".")
    if len(parts) != 5:
        return False, "توکن نامعتبر است", None, None
    admin_id_s, tx_id_s, exp_s, nonce, sig = parts
    if not (admin_id_s.isdigit() and tx_id_s.isdigit() and exp_s.isdigit() and nonce and len(sig) == 64):
        return False, "توکن نامعتبر است", None, None
    body = f"{admin_id_s}.{tx_id_s}.{exp_s}.{nonce}"
    expected = hmac.new(_get_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "توکن نامعتبر است", None, None
    if nonce in _consumed_nonces:
        return False, "این لینک قبلاً استفاده شده است", None, None
    if int(exp_s) < int(time.time()):
        _consumed_nonces[nonce] = time.time()
        return False, "این لینک منقضی شده است", None, None
    _consumed_nonces[nonce] = time.time()
    return True, None, int(admin_id_s), int(tx_id_s)

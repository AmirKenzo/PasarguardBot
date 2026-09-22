from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.utils.security.crypto import decrypt_data
from app.utils.security.secrets_cache import get_crypto_key
from config import BOT_TOKEN

_SESSION_HMAC_KEY: bytes | None = None


def validate_webapp_data(params: dict[str, str]) -> tuple[bool, str | None]:
    """Validate Telegram WebApp init data signature.

    Parameters
    ----------
    params: dict
        Query parameters or parsed initData payload.

    Returns
    -------
    tuple[bool, Optional[str]]
        ``(True, None)`` if signature is valid, otherwise ``(False, error_message)``.
    """
    if "hash" not in params:
        return False, "hash یافت نشد"

    signed_params = dict(params)
    hash_received = signed_params.pop("hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(signed_params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, hash_received):
        return False, "امضا معتبر نیست"

    return True, None


API_KEY_PREFIX = "ak_"


def generate_api_key() -> str:
    """Generate a long random profile login key (~256 bits of entropy)."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Deterministic lookup hash for an API key (the raw key is never stored as-is)."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def _session_signing_key() -> bytes:
    global _SESSION_HMAC_KEY
    if _SESSION_HMAC_KEY is None:
        _SESSION_HMAC_KEY = hashlib.sha256(get_crypto_key().encode("utf-8")).digest()
    return _SESSION_HMAC_KEY


SESSION_TOKEN_TTL_MINUTES = 60 * 24 * 14  # 14 days of inactivity before forced logout
_SESSION_RENEW_AFTER_SECONDS = 3600  # slide expiry forward once a token is over an hour old


def create_session_token(user_id: int, minutes: int = SESSION_TOKEN_TTL_MINUTES, session_version: int = 0) -> str:
    """Create an HMAC-signed session token for the given user ID.

    Format: ``{uid}.{exp}.{ver}.{hex_hmac}`` (no per-request KDF). ``ver`` is the
    user's `session_version` at issue time -- bumping it (e.g. after rotating the
    profile API key) makes every previously-issued token compare stale, without
    needing to track individual token strings. Logout on a single device still
    revokes just that token (see `revoke_session_token`).
    """
    uid = int(user_id)
    exp = int(time.time()) + int(minutes) * 60
    ver = int(session_version)
    body = f"{uid}.{exp}.{ver}"
    sig = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse_hmac_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None] | None:
    """Parse HMAC session token. Returns None if token is not HMAC-shaped."""
    parts = token.split(".")
    if len(parts) != 4:
        return None
    uid_s, exp_s, ver_s, sig = parts
    if not (uid_s.isdigit() and exp_s.isdigit() and ver_s.isdigit() and len(sig) == 64):
        return None
    body = f"{uid_s}.{exp_s}.{ver_s}"
    expected = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "توکن نامعتبر است", None
    uid = int(uid_s)
    exp = int(exp_s)
    if not uid:
        return False, "توکن نامعتبر است", None
    if exp < int(time.time()):
        return False, "نشست منقضی شده است", None
    return True, None, {"uid": uid, "exp": exp, "ver": int(ver_s)}


def _parse_legacy_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Decrypt and parse legacy AES-CFB session tokens (predate session_version; ver=0)."""
    try:
        data = json.loads(decrypt_data(token))
        uid = int(data.get("uid", 0))
        exp = int(data.get("exp", 0))
        if not uid:
            return False, "توکن نامعتبر است", None
        if exp < int(time.time()):
            return False, "نشست منقضی شده است", None
        return True, None, {"uid": uid, "exp": exp, "ver": 0}
    except Exception:
        return False, "توکن نامعتبر است", None


def parse_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Parse session token; prefers HMAC, falls back to legacy AES tokens."""
    token = (token or "").strip()
    if not token:
        return False, "توکن نامعتبر است", None
    hmac_result = _parse_hmac_session_token(token)
    if hmac_result is not None:
        return hmac_result
    return _parse_legacy_session_token(token)


def maybe_renew_session_token(token: str) -> str | None:
    """Slide an HMAC session token's expiry forward on active use.

    Returns a freshly-signed token (same uid/session_version, full TTL) when
    ``token`` is valid and older than the renewal grace period. Returns
    ``None`` when there is nothing to do -- token is still fresh, invalid,
    expired, or a legacy (non-HMAC) token, so the caller should keep using
    what it already has.
    """
    result = _parse_hmac_session_token(token)
    if result is None:
        return None
    ok, _err, payload = result
    if not ok or not payload:
        return None
    issued_at = payload["exp"] - SESSION_TOKEN_TTL_MINUTES * 60
    if time.time() - issued_at < _SESSION_RENEW_AFTER_SECONDS:
        return None
    return create_session_token(payload["uid"], session_version=payload["ver"])


async def parse_session_token_async(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Async parse: HMAC stays on-loop; legacy AES decrypt runs in a worker thread."""
    token = (token or "").strip()
    if not token:
        return False, "توکن نامعتبر است", None
    hmac_result = _parse_hmac_session_token(token)
    if hmac_result is not None:
        return hmac_result
    return await asyncio.to_thread(_parse_legacy_session_token, token)

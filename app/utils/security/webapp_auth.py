from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
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


def _session_signing_key() -> bytes:
    global _SESSION_HMAC_KEY
    if _SESSION_HMAC_KEY is None:
        _SESSION_HMAC_KEY = hashlib.sha256(get_crypto_key().encode("utf-8")).digest()
    return _SESSION_HMAC_KEY


def create_session_token(user_id: int, minutes: int = 120) -> str:
    """Create an HMAC-signed session token for the given user ID.

    Format: ``{uid}.{exp}.{hex_hmac}`` (no per-request KDF). Logout revokes the
    token itself (see `revoke_session_token`) instead of a per-user DB version.
    """
    uid = int(user_id)
    exp = int(time.time()) + int(minutes) * 60
    body = f"{uid}.{exp}"
    sig = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse_hmac_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None] | None:
    """Parse HMAC session token. Returns None if token is not HMAC-shaped."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    uid_s, exp_s, sig = parts
    if not (uid_s.isdigit() and exp_s.isdigit() and len(sig) == 64):
        return None
    body = f"{uid_s}.{exp_s}"
    expected = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "توکن نامعتبر است", None
    uid = int(uid_s)
    exp = int(exp_s)
    if not uid:
        return False, "توکن نامعتبر است", None
    if exp < int(time.time()):
        return False, "نشست منقضی شده است", None
    return True, None, {"uid": uid, "exp": exp}


def _parse_legacy_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Decrypt and parse legacy AES-CFB session tokens."""
    try:
        data = json.loads(decrypt_data(token))
        uid = int(data.get("uid", 0))
        exp = int(data.get("exp", 0))
        if not uid:
            return False, "توکن نامعتبر است", None
        if exp < int(time.time()):
            return False, "نشست منقضی شده است", None
        return True, None, {"uid": uid, "exp": exp}
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


async def parse_session_token_async(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Async parse: HMAC stays on-loop; legacy AES decrypt runs in a worker thread."""
    token = (token or "").strip()
    if not token:
        return False, "توکن نامعتبر است", None
    hmac_result = _parse_hmac_session_token(token)
    if hmac_result is not None:
        return hmac_result
    return await asyncio.to_thread(_parse_legacy_session_token, token)

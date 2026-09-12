from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
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


def hash_password(password: str) -> str:
    """Return a salted password hash.

    Existing SHA256 hashes are still accepted by verify_password for backward
    compatibility; newly stored passwords use PBKDF2.
    """

    salt = os.urandom(16).hex()
    rounds = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), rounds).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, digest = stored_hash.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                bytes.fromhex(salt),
                int(rounds),
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except (ValueError, TypeError):
            return False

    # Legacy hashes created by the old helper.
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored_hash)


async def hash_password_async(password: str) -> str:
    """Hash password off the event loop (PBKDF2 is CPU-heavy)."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, stored_hash: str | None) -> bool:
    """Verify password off the event loop (PBKDF2 is CPU-heavy)."""
    return await asyncio.to_thread(verify_password, password, stored_hash)


def _session_signing_key() -> bytes:
    global _SESSION_HMAC_KEY
    if _SESSION_HMAC_KEY is None:
        _SESSION_HMAC_KEY = hashlib.sha256(get_crypto_key().encode("utf-8")).digest()
    return _SESSION_HMAC_KEY


def create_session_token(user_id: int, version: int = 0, minutes: int = 120) -> str:
    """Create an HMAC-signed session token for the given user ID.

    Includes a per-user session version for instant invalidation on logout.
    Format: ``{uid}.{ver}.{exp}.{hex_hmac}`` (no per-request KDF).
    """
    uid = int(user_id)
    ver = int(version)
    exp = int(time.time()) + int(minutes) * 60
    body = f"{uid}.{ver}.{exp}"
    sig = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _parse_hmac_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None] | None:
    """Parse HMAC session token. Returns None if token is not HMAC-shaped."""
    parts = token.split(".")
    if len(parts) != 4:
        return None
    uid_s, ver_s, exp_s, sig = parts
    if not (uid_s.isdigit() and ver_s.isdigit() and exp_s.isdigit() and len(sig) == 64):
        return None
    body = f"{uid_s}.{ver_s}.{exp_s}"
    expected = hmac.new(_session_signing_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "توکن نامعتبر است", None
    uid = int(uid_s)
    ver = int(ver_s)
    exp = int(exp_s)
    if not uid:
        return False, "توکن نامعتبر است", None
    if exp < int(time.time()):
        return False, "نشست منقضی شده است", None
    return True, None, {"uid": uid, "ver": ver, "exp": exp}


def _parse_legacy_session_token(token: str) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Decrypt and parse legacy AES-CFB session tokens."""
    try:
        data = json.loads(decrypt_data(token))
        uid = int(data.get("uid", 0))
        ver = int(data.get("ver", 0))
        exp = int(data.get("exp", 0))
        if not uid:
            return False, "توکن نامعتبر است", None
        if exp < int(time.time()):
            return False, "نشست منقضی شده است", None
        return True, None, {"uid": uid, "ver": ver, "exp": exp}
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
    """Async parse: HMAC stays on-loop; legacy AES+PBKDF2 runs in a worker thread."""
    token = (token or "").strip()
    if not token:
        return False, "توکن نامعتبر است", None
    hmac_result = _parse_hmac_session_token(token)
    if hmac_result is not None:
        return hmac_result
    return await asyncio.to_thread(_parse_legacy_session_token, token)

"""In-memory auth state shared across WebApp router feature modules.

Holds OTP sessions, revoked session tokens, and per-service renewal locks.
This is process-local (not shared across workers) and reset on restart —
acceptable for the current single-process deployment.
"""

import time as time_module
from asyncio import Lock
from collections import defaultdict
from contextvars import ContextVar
from typing import Any

# In-memory OTP sessions: { key: { code, user_id, exp, attempts } }
otp_sessions: dict[str, dict[str, Any]] = {}
# In-memory revoked session tokens: token -> revoke_monotonic_deadline
revoked_tokens: dict[str, float] = {}
# In-memory failed API key login attempts per client IP, for basic brute-force throttling.
api_key_login_failures: dict[str, list[float]] = {}
# Per-service lock to prevent concurrent double-renewal
renew_confirm_locks: defaultdict[int, Lock] = defaultdict(Lock)

# Request-scoped auth extracted from secure headers by middleware.
# Tuple: (session_token | None, init_data | None)
webapp_auth_headers: ContextVar[tuple[str | None, str | None]] = ContextVar(
    "webapp_auth_headers",
    default=(None, None),
)

_auth_state_last_prune = 0.0
_AUTH_STATE_PRUNE_INTERVAL_SEC = 60.0
_REVOKED_TOKEN_TTL_SEC = 86400.0
_API_KEY_LOGIN_WINDOW_SEC = 300.0
_API_KEY_LOGIN_MAX_ATTEMPTS = 10


def prune_auth_state(now: float | None = None) -> None:
    """Drop expired OTP sessions and aged revoked-token/api-key-attempt entries."""
    global _auth_state_last_prune
    now = time_module.time() if now is None else now
    if now - _auth_state_last_prune < _AUTH_STATE_PRUNE_INTERVAL_SEC:
        return
    _auth_state_last_prune = now
    expired_otp = [key for key, sess in otp_sessions.items() if float(sess.get("exp") or 0) <= now]
    for key in expired_otp:
        otp_sessions.pop(key, None)
    expired_revoked = [token for token, until in revoked_tokens.items() if until <= now]
    for token in expired_revoked:
        revoked_tokens.pop(token, None)
    stale_ips = [
        ip
        for ip, attempts in api_key_login_failures.items()
        if not attempts or now - max(attempts) > _API_KEY_LOGIN_WINDOW_SEC
    ]
    for ip in stale_ips:
        api_key_login_failures.pop(ip, None)


def revoke_session_token(token: str) -> None:
    prune_auth_state()
    revoked_tokens[token] = time_module.time() + _REVOKED_TOKEN_TTL_SEC


def otp_key(phone: str) -> str:
    return f"otp:{phone}"


def record_api_key_login_failure(client_ip: str) -> None:
    now = time_module.time()
    attempts = [t for t in api_key_login_failures.get(client_ip, []) if now - t < _API_KEY_LOGIN_WINDOW_SEC]
    attempts.append(now)
    api_key_login_failures[client_ip] = attempts


def is_api_key_login_blocked(client_ip: str) -> bool:
    now = time_module.time()
    attempts = [t for t in api_key_login_failures.get(client_ip, []) if now - t < _API_KEY_LOGIN_WINDOW_SEC]
    api_key_login_failures[client_ip] = attempts
    return len(attempts) >= _API_KEY_LOGIN_MAX_ATTEMPTS


def get_header_auth() -> tuple[str | None, str | None]:
    """Return (session_token, init_data) from the current request headers, if any."""
    return webapp_auth_headers.get()

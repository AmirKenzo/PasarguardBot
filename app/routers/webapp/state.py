"""In-memory auth state shared across WebApp router feature modules.

Holds OTP sessions, revoked session tokens, and per-service renewal locks.
This is process-local (not shared across workers) and reset on restart —
acceptable for the current single-process deployment.
"""

import time as time_module
from asyncio import Lock
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

# In-memory OTP sessions: { key: { code, user_id, exp, attempts } }
otp_sessions: dict[str, dict[str, Any]] = {}
# In-memory revoked session tokens: token -> revoke_monotonic_deadline
revoked_tokens: dict[str, float] = {}
# In-memory failed API key login attempts per client IP, for basic brute-force throttling.
api_key_login_failures: dict[str, list[float]] = {}
otp_start_history: dict[str, list[float]] = {}
otp_failure_history: dict[str, list[float]] = {}
renew_confirm_locks: dict[int, list] = {}


@asynccontextmanager
async def renew_confirm_lock(code: int) -> AsyncIterator[None]:
    entry = renew_confirm_locks.setdefault(code, [Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if entry[1] == 0 and renew_confirm_locks.get(code) is entry:
            del renew_confirm_locks[code]


# Request-scoped auth extracted from secure headers by middleware.
# Tuple: (session_token | None, init_data | None)
webapp_auth_headers: ContextVar[tuple[str | None, str | None]] = ContextVar(
    "webapp_auth_headers",
    default=(None, None),
)

verified_session_tokens: ContextVar[set[str] | None] = ContextVar("verified_session_tokens", default=None)


def mark_session_verified(token: str) -> None:
    holder = verified_session_tokens.get()
    if holder is not None:
        holder.add(token)


_auth_state_last_prune = 0.0
_AUTH_STATE_PRUNE_INTERVAL_SEC = 60.0
_REVOKED_TOKEN_TTL_SEC = 86400.0
_API_KEY_LOGIN_WINDOW_SEC = 300.0
_API_KEY_LOGIN_MAX_ATTEMPTS = 10
OTP_START_WINDOW_SEC = 900.0
OTP_MAX_STARTS_PER_PHONE = 3
OTP_MAX_STARTS_PER_IP = 10
OTP_FAILURE_WINDOW_SEC = 3600.0
OTP_MAX_FAILURES_PER_PHONE = 10


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
    _prune_history(otp_start_history, OTP_START_WINDOW_SEC, now)
    _prune_history(otp_failure_history, OTP_FAILURE_WINDOW_SEC, now)


def _prune_history(history: dict[str, list[float]], window: float, now: float) -> None:
    stale = [key for key, stamps in history.items() if not stamps or now - max(stamps) > window]
    for key in stale:
        history.pop(key, None)


def _recent(history: dict[str, list[float]], key: str, window: float, now: float) -> list[float]:
    stamps = [t for t in history.get(key, []) if now - t < window]
    history[key] = stamps
    return stamps


def is_otp_locked(phone_key: str, now: float | None = None) -> bool:
    """True when this phone has too many wrong OTP guesses in the failure window."""
    now = time_module.time() if now is None else now
    return len(_recent(otp_failure_history, phone_key, OTP_FAILURE_WINDOW_SEC, now)) >= OTP_MAX_FAILURES_PER_PHONE


def try_register_otp_start(phone_key: str, ip_key: str, now: float | None = None) -> bool:
    """Record an OTP request if the phone and IP are under their limits; return False when throttled."""
    now = time_module.time() if now is None else now
    if is_otp_locked(phone_key, now):
        return False
    phone_starts = _recent(otp_start_history, phone_key, OTP_START_WINDOW_SEC, now)
    ip_starts = _recent(otp_start_history, ip_key, OTP_START_WINDOW_SEC, now)
    if len(phone_starts) >= OTP_MAX_STARTS_PER_PHONE or len(ip_starts) >= OTP_MAX_STARTS_PER_IP:
        return False
    phone_starts.append(now)
    ip_starts.append(now)
    return True


def record_otp_failure(phone_key: str, now: float | None = None) -> None:
    now = time_module.time() if now is None else now
    _recent(otp_failure_history, phone_key, OTP_FAILURE_WINDOW_SEC, now).append(now)


def clear_otp_failures(phone_key: str) -> None:
    otp_failure_history.pop(phone_key, None)


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

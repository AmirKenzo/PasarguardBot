"""Lightweight Zibal settings helpers (no Telegram/DB imports, safe to use from keyboards)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from config import ADMIN_ID, WEBAPP_URL

BASE_URL = "https://gateway.zibal.ir"
# Zibal's public test merchant: payments are simulated on the same gateway, no account needed.
SANDBOX_MERCHANT = "zibal"
MERCHANT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
CALLBACK_PATH = "/api/payments/zibal/callback"


def is_sandbox(settings) -> bool:
    return bool(getattr(settings, "zibal_sandbox", True))


def stored_merchant(settings) -> str:
    return str(getattr(settings, "zibal_merchant", "") or "").strip()


def merchant_for(settings, sandbox: bool | None = None) -> str:
    """Merchant to send; test mode always uses Zibal's public test merchant."""
    sandbox = is_sandbox(settings) if sandbox is None else sandbox
    return SANDBOX_MERCHANT if sandbox else stored_merchant(settings)


def is_valid_merchant(value: str) -> bool:
    value = (value or "").strip()
    return bool(MERCHANT_PATTERN.match(value)) and value != SANDBOX_MERCHANT


def start_pay_url(track_id: str) -> str:
    return f"{BASE_URL}/start/{track_id}"


def callback_url() -> str | None:
    """Public return URL for the buyer, only when the app is served over https."""
    parsed = urlparse(WEBAPP_URL or "")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return f"https://{parsed.netloc}{CALLBACK_PATH}"


def is_ready(settings) -> bool:
    """Enabled, reachable from the gateway, and holding a merchant (or in test mode)."""
    if not settings or not getattr(settings, "zibal_enabled", False) or not callback_url():
        return False
    return bool(merchant_for(settings))


def is_available_for(settings, user_id: int | None) -> bool:
    """Test mode never moves real money, so it is only offered to admins."""
    if not is_ready(settings):
        return False
    return not is_sandbox(settings) or (user_id is not None and int(user_id) in ADMIN_ID)


def deposit_limits(settings) -> tuple[int, int]:
    return (
        int(getattr(settings, "zibal_deposit_min", 0) or 0),
        int(getattr(settings, "zibal_deposit_max", 0) or 0),
    )


def bonus_percent(settings) -> int:
    if not getattr(settings, "zibal_bonus_enabled", False):
        return 0
    return int(getattr(settings, "zibal_bonus_percent", 0) or 0)


def mask_merchant(merchant: str | None) -> str:
    merchant = (merchant or "").strip()
    if not merchant:
        return ""
    return f"{merchant[:4]}****{merchant[-4:]}" if len(merchant) > 10 else "****"

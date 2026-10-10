"""Lightweight Zarinpal settings helpers (no Telegram/DB imports, safe to use from keyboards)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from config import ADMIN_ID, WEBAPP_URL

LIVE_BASE_URL = "https://payment.zarinpal.com"
SANDBOX_BASE_URL = "https://sandbox.zarinpal.com"
# The sandbox accepts any UUID-shaped merchant id, so test mode works without a Zarinpal account.
SANDBOX_MERCHANT_ID = "00000000-0000-0000-0000-000000000000"
MERCHANT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
CALLBACK_PATH = "/api/payments/zarinpal/callback"


def is_sandbox(settings) -> bool:
    return bool(getattr(settings, "zarinpal_sandbox", True))


def stored_merchant_id(settings) -> str:
    return str(getattr(settings, "zarinpal_merchant_id", "") or "").strip()


def merchant_id_for(settings, sandbox: bool | None = None) -> str:
    """Merchant id to send; sandbox falls back to a placeholder UUID when none is stored."""
    sandbox = is_sandbox(settings) if sandbox is None else sandbox
    merchant = stored_merchant_id(settings)
    if sandbox:
        return merchant if MERCHANT_ID_PATTERN.match(merchant) else SANDBOX_MERCHANT_ID
    return merchant


def is_valid_merchant_id(value: str) -> bool:
    return bool(MERCHANT_ID_PATTERN.match((value or "").strip()))


def base_url(sandbox: bool) -> str:
    return SANDBOX_BASE_URL if sandbox else LIVE_BASE_URL


def start_pay_url(authority: str, sandbox: bool) -> str:
    return f"{base_url(sandbox)}/pg/StartPay/{authority}"


def callback_url() -> str | None:
    """Public return URL for the buyer, only when the app is served over https."""
    parsed = urlparse(WEBAPP_URL or "")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return f"https://{parsed.netloc}{CALLBACK_PATH}"


def is_ready(settings) -> bool:
    """Enabled, reachable from the gateway, and holding a merchant id (or in test mode)."""
    if not settings or not getattr(settings, "zarinpal_enabled", False) or not callback_url():
        return False
    return bool(merchant_id_for(settings))


def is_available_for(settings, user_id: int | None) -> bool:
    """Test mode never credits real money, so it is only offered to admins."""
    if not is_ready(settings):
        return False
    return not is_sandbox(settings) or (user_id is not None and int(user_id) in ADMIN_ID)


def deposit_limits(settings) -> tuple[int, int]:
    return (
        int(getattr(settings, "zarinpal_deposit_min", 0) or 0),
        int(getattr(settings, "zarinpal_deposit_max", 0) or 0),
    )


def bonus_percent(settings) -> int:
    if not getattr(settings, "zarinpal_bonus_enabled", False):
        return 0
    return int(getattr(settings, "zarinpal_bonus_percent", 0) or 0)


def mask_merchant(merchant: str | None) -> str:
    merchant = (merchant or "").strip()
    if not merchant:
        return ""
    return f"{merchant[:4]}****{merchant[-4:]}" if len(merchant) > 10 else "****"

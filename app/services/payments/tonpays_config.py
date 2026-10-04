"""Lightweight TonPays settings helpers (no Telegram/DB imports, safe to use from keyboards)."""

from __future__ import annotations

from urllib.parse import urlparse

from config import WEBAPP_URL

MODE_STANDARD = "standard"
MODE_CUSTOM = "custom"


def gateway_mode(settings) -> str:
    mode = str(getattr(settings, "tonpays_mode", MODE_STANDARD) or MODE_STANDARD)
    return mode if mode in (MODE_STANDARD, MODE_CUSTOM) else MODE_STANDARD


def api_key_for(settings, mode: str) -> str:
    attr = "tonpays_custom_key" if mode == MODE_CUSTOM else "tonpays_api_key"
    return str(getattr(settings, attr, "") or "").strip()


def is_ready(settings) -> bool:
    """Enabled and holding a key for the selected mode."""
    return bool(
        settings and getattr(settings, "tonpays_enabled", False) and api_key_for(settings, gateway_mode(settings))
    )


def deposit_limits(settings) -> tuple[int, int]:
    return int(getattr(settings, "tonpays_deposit_min", 0) or 0), int(getattr(settings, "tonpays_deposit_max", 0) or 0)


def callback_url() -> str | None:
    """Public webhook URL, only when the app is served over https."""
    parsed = urlparse(WEBAPP_URL or "")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return f"https://{parsed.netloc}/api/payments/tonpays/callback"


def mask_key(key: str | None) -> str:
    key = (key or "").strip()
    if not key:
        return "تنظیم نشده"
    return f"{key[:4]}****{key[-4:]}" if len(key) > 10 else "****"

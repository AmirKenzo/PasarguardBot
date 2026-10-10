"""Per-gateway settings stored under payment_settings["ir_gateways"][<key>] (no Telegram/DB imports)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from app.services.payments.ir_gateways.providers import GATEWAYS, IrGatewayProvider, get_provider
from config import ADMIN_ID, WEBAPP_URL

DEFAULT_GATEWAY_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "sandbox": True,
    "merchant": "",
    "deposit_min": 10000,
    "deposit_max": 10000000,
    "bonus_enabled": False,
    "bonus_percent": 0,
}


def _all(settings) -> dict[str, Any]:
    raw = getattr(settings, "ir_gateways", None) if settings is not None else None
    return raw if isinstance(raw, dict) else {}


def gateway_settings(settings, key: str) -> dict[str, Any]:
    """This gateway's settings merged over the defaults (a fresh copy, safe to modify)."""
    merged = deepcopy(DEFAULT_GATEWAY_SETTINGS)
    stored = _all(settings).get(key)
    if isinstance(stored, dict):
        merged.update({k: v for k, v in stored.items() if k in DEFAULT_GATEWAY_SETTINGS})
    return merged


def updated_settings(settings, key: str, **changes: Any) -> dict[str, Any]:
    """The whole ir_gateways dict with only `key` changed, ready for update_setting(ir_gateways=...)."""
    everything = deepcopy(_all(settings))
    current = gateway_settings(settings, key)
    current.update({k: v for k, v in changes.items() if k in DEFAULT_GATEWAY_SETTINGS})
    everything[key] = current
    return everything


def is_sandbox(settings, key: str) -> bool:
    return bool(gateway_settings(settings, key)["sandbox"])


def stored_merchant(settings, key: str) -> str:
    return str(gateway_settings(settings, key)["merchant"] or "").strip()


def merchant_for(settings, key: str, sandbox: bool | None = None) -> str:
    sandbox = is_sandbox(settings, key) if sandbox is None else sandbox
    return get_provider(key).merchant_for(stored_merchant(settings, key), sandbox)


def callback_url(key: str) -> str | None:
    """Public return URL for the buyer, only when the app is served over https."""
    parsed = urlparse(WEBAPP_URL or "")
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return f"https://{parsed.netloc}/api/payments/{key}/callback"


def is_ready(settings, key: str) -> bool:
    """Enabled, reachable from the gateway, and holding a merchant (or in test mode)."""
    if key not in GATEWAYS or not settings or not callback_url(key):
        return False
    if not gateway_settings(settings, key)["enabled"]:
        return False
    return bool(merchant_for(settings, key))


def is_available_for(settings, key: str, user_id: int | None) -> bool:
    """Test mode moves no real money, so it is only offered to admins."""
    if not is_ready(settings, key):
        return False
    return not is_sandbox(settings, key) or (user_id is not None and int(user_id) in ADMIN_ID)


def available_gateways(settings, user_id: int | None) -> list[IrGatewayProvider]:
    return [provider for key, provider in GATEWAYS.items() if is_available_for(settings, key, user_id)]


def deposit_limits(settings, key: str) -> tuple[int, int]:
    values = gateway_settings(settings, key)
    return int(values["deposit_min"] or 0), int(values["deposit_max"] or 0)


def bonus_percent(settings, key: str) -> int:
    values = gateway_settings(settings, key)
    return int(values["bonus_percent"] or 0) if values["bonus_enabled"] else 0


def mask_merchant(merchant: str | None) -> str:
    merchant = (merchant or "").strip()
    if not merchant:
        return ""
    return f"{merchant[:4]}****{merchant[-4:]}" if len(merchant) > 10 else "****"

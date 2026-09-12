import base64
import json
import time
from typing import Literal

PanelCookieLocale = Literal["fa", "en"]


def _decode_jwt_payload(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def panel_cookie_remaining_seconds(cookie: str | None) -> int | None:
    if not cookie or not cookie.strip():
        return None
    payload = _decode_jwt_payload(cookie.strip())
    if not payload:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int | float):
        return None
    return int(exp) - int(time.time())


def panel_cookie_needs_refresh(cookie: str | None, *, min_remaining_seconds: int = 3600) -> bool:
    remaining = panel_cookie_remaining_seconds(cookie)
    if remaining is None:
        return True
    return remaining < min_remaining_seconds


def _split_remaining_seconds(total: int) -> tuple[int, int, int]:
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return days, hours, minutes


def format_panel_cookie_validity(cookie: str | None, *, locale: PanelCookieLocale = "fa") -> str:
    remaining = panel_cookie_remaining_seconds(cookie)
    if remaining is None:
        return "invalid" if locale == "en" else "نامعتبر"
    if remaining <= 0:
        return "expired" if locale == "en" else "منقضی شده"

    days, hours, minutes = _split_remaining_seconds(remaining)
    if locale == "en":
        return f"{days}D {hours}H {minutes}M"
    return f"معتبر تا {days} روز و {hours} ساعت و {minutes} دقیقه دیگر"

"""Custom volume/duration VPN purchase helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.services.panels.settings import (
    calculate_custom_buy_price_from_settings,
    is_custom_buy_ready,
    panel_custom_buy_settings,
)

CUSTOM_PLAN_ID = "custom"


def build_custom_buy_plan(
    *,
    storage_gb: float,
    duration_days: int,
    price: int,
    ip_limit: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=CUSTOM_PLAN_ID,
        price=int(price),
        storage=float(storage_gb),
        duration=int(duration_days),
        plan_type="volume",
        data_limit_reset_strategy="no_reset",
        ip_limit=int(ip_limit or 0),
        name="خرید دلخواه",
    )


def is_custom_plan_id(plan_id: Any) -> bool:
    return str(plan_id or "").strip().lower() == CUSTOM_PLAN_ID


def format_gb_value(value: float) -> str:
    number = float(value)
    return str(int(number)) if number == int(number) else f"{number:g}"


def validate_custom_gb(
    panel,
    raw: str,
    *,
    settings: dict[str, Any] | None = None,
) -> tuple[float | None, str | None]:
    cfg = settings or panel_custom_buy_settings(panel)
    text = (raw or "").strip().replace(",", ".")
    try:
        value = float(text)
    except TypeError, ValueError:
        return None, "❌ حجم باید عدد باشد.\n\nمثال: 30"
    if value <= 0:
        return None, "❌ حجم باید بزرگ‌تر از صفر باشد."
    min_gb = float(cfg["min_gb"])
    max_gb = float(cfg["max_gb"])
    if value < min_gb or value > max_gb:
        return None, f"❌ حجم باید بین {format_gb_value(min_gb)} تا {format_gb_value(max_gb)} گیگ باشد."
    return value, None


def validate_custom_days(
    panel,
    raw: str,
    *,
    settings: dict[str, Any] | None = None,
) -> tuple[int | None, str | None]:
    cfg = settings or panel_custom_buy_settings(panel)
    text = (raw or "").strip().replace(",", "")
    if not text.isdigit():
        return None, "❌ تعداد روز باید عدد صحیح باشد.\n\nمثال: 30"
    value = int(text)
    min_days = int(cfg["min_days"])
    max_days = int(cfg["max_days"])
    if value < min_days or value > max_days:
        return None, f"❌ مدت باید بین {min_days} تا {max_days} روز باشد."
    return value, None


def build_custom_plan_for_panel(panel, *, storage_gb: float, duration_days: int) -> SimpleNamespace | None:
    settings = panel_custom_buy_settings(panel)
    if not is_custom_buy_ready(settings):
        return None
    price = calculate_custom_buy_price_from_settings(settings, storage_gb=storage_gb, duration_days=duration_days)
    return build_custom_buy_plan(
        storage_gb=storage_gb,
        duration_days=duration_days,
        price=price,
        ip_limit=int(settings["ip_limit"]),
    )

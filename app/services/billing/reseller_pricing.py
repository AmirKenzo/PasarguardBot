"""Reseller plan pricing calculations."""

from __future__ import annotations

from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_plans import ResellerPlan

VOLUME_MODES = ("per_gb", "per_tb")


def requires_volume_input(plan: ResellerPlan) -> bool:
    return plan.pricing_mode in VOLUME_MODES


def requires_wallet_for_purchase(plan: ResellerPlan) -> bool:
    return plan.pricing_mode in ("hourly", "usage")


def calculate_purchase_price(plan: ResellerPlan, volume: float | None = None) -> int:
    mode = plan.pricing_mode
    if mode == "fixed":
        return int(plan.price)
    if mode in VOLUME_MODES:
        vol = float(volume or 0)
        if vol <= 0:
            return 0
        return round(float(plan.unit_price) * vol)
    if mode == "hourly":
        return int(plan.price)
    if mode == "usage":
        return int(plan.price)
    return int(plan.price)


def validate_volume(plan: ResellerPlan, volume: float) -> tuple[bool, str]:
    if plan.pricing_mode not in VOLUME_MODES:
        return True, ""
    if volume <= 0:
        return False, "حجم باید بزرگ‌تر از صفر باشد."
    if plan.min_volume and volume < float(plan.min_volume):
        return False, f"حداقل حجم مجاز {plan.min_volume:g} است."
    if plan.max_volume and volume > float(plan.max_volume):
        return False, f"حداکثر حجم مجاز {plan.max_volume:g} است."
    if plan.volume_step and plan.volume_step > 0:
        step = float(plan.volume_step)
        remainder = (volume - float(plan.min_volume or 0)) % step
        if remainder > 1e-9 and abs(remainder - step) > 1e-9:
            return False, f"حجم باید مضربی از {step:g} باشد."
    return True, ""


def pricing_mode_label(mode: str) -> str:
    return {
        "fixed": "پلن ثابت",
        "per_gb": "هر گیگابایت",
        "per_tb": "هر ترابایت",
        "hourly": "ساعتی",
        "usage": "مصرفی (بر اساس حجم مصرف)",
    }.get(mode, mode)


def pricing_mode_short_label(mode: str) -> str:
    return {
        "fixed": "ثابت",
        "per_gb": "گیگ",
        "per_tb": "ترا",
        "hourly": "ساعتی",
        "usage": "مصرفی",
    }.get(mode, mode)


def format_reseller_plan_price_short(plan: ResellerPlan) -> str:
    """Compact price snippet for inline buttons."""
    if plan.pricing_mode == "fixed":
        parts = [f"{int(plan.price):,}ت"]
        if plan.duration:
            parts.append(f"{plan.duration}روز")
        return " · ".join(parts)
    if plan.pricing_mode == "hourly":
        return f"{int(plan.unit_price):,}ت/س"
    if plan.pricing_mode == "per_tb":
        return f"{int(plan.unit_price):,}ت/ترا"
    if plan.pricing_mode == "per_gb":
        return f"{int(plan.unit_price):,}ت/گ"
    return f"{int(plan.unit_price):,}ت/گیگ"


def format_reseller_plan_button_short(plan: ResellerPlan) -> str:
    """Short default label for reseller plan inline buttons."""
    mode = pricing_mode_short_label(plan.pricing_mode)
    return f"{mode} · {format_reseller_plan_price_short(plan)}"


def format_reseller_plan_admin_list_label(plan: ResellerPlan) -> str:
    """Short label for admin plan list buttons."""
    status = "✅" if plan.enable else "❌"
    custom = (plan.display_button_text or "").strip()
    name = custom.split("\n", 1)[0].strip()[:20] if custom else ""
    price = format_reseller_plan_price_short(plan)
    if name:
        return f"#{plan.id} {name} · {price} {status}"
    return f"#{plan.id} · {price} {status}"


def volume_unit_label(mode: str) -> str:
    return "ترابایت" if mode == "per_tb" else "گیگابایت"


def resolve_live_unit_price(account: ResellerAccount, plan: ResellerPlan | None) -> float:
    """Bill and display using the current linked plan only — no purchase-time snapshot."""
    if not plan:
        return 0.0
    if plan.pricing_mode in ("hourly", "usage", "per_gb", "per_tb"):
        return float(plan.unit_price or 0)
    return float(plan.price or 0)

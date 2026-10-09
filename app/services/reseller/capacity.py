"""Extra reseller user slots; the price is set per plan (``addon_user_price``)."""

from __future__ import annotations

from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.reseller.addons import buy_addon
from app.services.reseller.plan_rules import ADDON_USERS, addon_price

CAPACITY_PRESETS: tuple[int, ...] = (5, 10, 20, 30, 50, 100)
CAPACITY_CUSTOM_MAX = 10_000


def validate_capacity_quantity(raw: str) -> tuple[int | None, str | None]:
    """Parse and validate a user-entered capacity quantity. Returns (quantity, error_message).

    Pure/in-memory — no I/O, so this stays a plain sync function rather than an unnecessary
    coroutine (matches ``validate_volume`` and the other reseller-pricing helpers in this codebase).
    """
    text = (raw or "").strip().replace(",", "").replace("،", "")
    if not text:
        return None, "لطفاً یک عدد وارد کنید."
    try:
        value = int(text)
    except ValueError:
        return None, "فقط عدد صحیح مثبت وارد کنید."
    if value <= 0:
        return None, "تعداد باید بزرگ‌تر از صفر باشد."
    if value > CAPACITY_CUSTOM_MAX:
        return None, f"حداکثر تعداد مجاز در هر خرید {CAPACITY_CUSTOM_MAX:,} کاربر است."
    return value, None


def capacity_price_per_user(plan) -> int:
    """Price of one extra user slot on ``plan``; 0 when the add-on is off."""
    return addon_price(plan, ADDON_USERS)


def calculate_capacity_price(plan, quantity: int) -> int:
    return capacity_price_per_user(plan) * int(quantity)


async def increase_reseller_capacity(
    account,
    panel,
    *,
    quantity: int,
    telegram_id: int,
    source: str = "preset",
    actor_id: int | None = None,
    actor_role: str | None = None,
) -> tuple[bool, str]:
    """Buy extra user slots; kept for older callers, the work is done by ``buy_addon``.

    Caller must hold the ``ADDON_LOCK`` user lock around this call.
    """
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    ok, message, _ = await buy_addon(
        account, panel, plan, ADDON_USERS, quantity, telegram_id=telegram_id, actor_id=actor_id, source=source
    )
    return ok, message

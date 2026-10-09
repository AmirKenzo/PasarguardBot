"""Add-ons a reseller buys on top of their plan: extra days, extra volume and extra user slots.

Shared by the bot and the user web app. Each purchase follows one pattern: validate against the
plan's rules, debit the wallet, apply on the panel, store, and refund if the panel step fails.
Callers hold a per-user lock (``ADDON_LOCK``) around ``buy_addon``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pasarguard import AdminModify, RoleLimits

from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.user import debit_Money_if_sufficient, update_Money
from app.logger import get_logger
from app.services.panels.admins import activate_reseller_admin, get_reseller_admin, modify_reseller_admin
from app.services.reseller.logging import (
    EVENT_CAPACITY,
    EVENT_EXTRA_DAYS,
    EVENT_EXTRA_VOLUME,
    send_reseller_log,
)
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS, ADDON_VOLUME, addon_price
from app.utils.formatting.conversions import gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size

log = get_logger(__name__)

# Same lock name the bot used for capacity, so a tap in Telegram and one in the web app can't both charge.
ADDON_LOCK = "reseller_capacity_buy"
ADDON_MAX_QUANTITY = {ADDON_DAYS: 3650, ADDON_VOLUME: 100_000, ADDON_USERS: 10_000}
ADDON_LABELS = {ADDON_DAYS: "روز اضافه", ADDON_VOLUME: "حجم اضافه", ADDON_USERS: "یوزر اضافه"}


@dataclass
class AddonQuote:
    """What one add-on purchase costs and changes; ``before``/``after`` are in the add-on's unit
    (expiry timestamp for days, bytes for volume, user count for users)."""

    addon: str
    quantity: int
    unit_price: int
    total: int
    before: int
    after: int


def _locked_error(account) -> str | None:
    if account.status == "admin_paused":
        return "این نمایندگی توسط ادمین غیرفعال شده است."
    return None


async def quote_addon(account, plan, addon: str, quantity: int) -> tuple[AddonQuote | None, str | None]:
    """Validate and price an add-on without touching anything. Returns (quote, error)."""
    if addon not in ADDON_MAX_QUANTITY:
        return None, "افزودنی نامعتبر است."
    error = _locked_error(account)
    if error:
        return None, error
    if plan is None:
        return None, "پلن این نمایندگی پیدا نشد."
    unit_price = addon_price(plan, addon)
    if unit_price <= 0:
        return None, f"{ADDON_LABELS[addon]} برای این پلن فعال نیست."
    if not isinstance(quantity, int) or quantity <= 0:
        return None, "تعداد باید بیشتر از صفر باشد."
    if quantity > ADDON_MAX_QUANTITY[addon]:
        return None, f"حداکثر {ADDON_MAX_QUANTITY[addon]:,} در هر خرید مجاز است."

    if addon == ADDON_DAYS:
        if not account.expiration_time:
            return None, "این نمایندگی تاریخ انقضا ندارد."
        before = int(account.expiration_time)
        after = max(before, Time_Date()["stamp"]) + quantity * 86400
    elif addon == ADDON_VOLUME:
        if account.status == "expired":
            return None, "نمایندگی منقضی شده است؛ ابتدا آن را تمدید کنید."
        before = int(account.data_limit or 0)
        if before <= 0:
            return None, "حجم این نمایندگی نامحدود است."
        after = before + int(gigabytes_to_bytes(quantity))
    else:
        before = int(account.max_users or 0)
        if before <= 0:
            return None, "این نمایندگی محدودیت تعداد یوزر ندارد."
        after = before + quantity

    return AddonQuote(addon, quantity, unit_price, unit_price * quantity, before, after), None


async def _apply_on_panel(account, panel, quote: AddonQuote) -> dict:
    """Push the add-on to the panel and return the DB columns to store."""
    if quote.addon == ADDON_DAYS:
        columns: dict = {"expiration_time": quote.after}
        if account.status == "expired":
            await activate_reseller_admin(panel, account.panel_admin_id)
            columns["status"] = "active"
        return columns

    current = await get_reseller_admin(panel, account.panel_admin_id)
    if not current:
        raise RuntimeError("admin not found on panel")
    if quote.addon == ADDON_VOLUME:
        panel_limit = int(getattr(current, "data_limit", 0) or 0) or quote.before
        new_limit = panel_limit + (quote.after - quote.before)
        await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(data_limit=new_limit))
        return {"data_limit": new_limit}

    overrides = current.permission_overrides
    if overrides is not None:
        overrides = overrides.model_copy(update={"max_users": quote.after})
    else:
        overrides = RoleLimits(max_users=quote.after)
    await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(permission_overrides=overrides))
    return {"max_users": quote.after, "extra_users": int(account.extra_users or 0) + quote.quantity}


async def buy_addon(
    account,
    panel,
    plan,
    addon: str,
    quantity: int,
    *,
    telegram_id: int,
    actor_id: int | None = None,
    source: str = "bot",
) -> tuple[bool, str, AddonQuote | None]:
    """Charge and apply one add-on. Returns (ok, message, quote)."""
    if panel is None:
        return False, "پنل یافت نشد.", None
    ok, fresh = await ResellerAccountCRUD().get_account(account.code)
    if not ok or int(fresh.telegram_id) != int(telegram_id):
        return False, "نمایندگی یافت نشد.", None
    account = fresh
    quote, error = await quote_addon(account, plan, addon, quantity)
    if error:
        return False, error, None

    new_balance = await debit_Money_if_sufficient(user_id=telegram_id, amount=quote.total)
    if new_balance is None:
        return False, f"موجودی کافی نیست. نیاز: {quote.total:,} تومان", quote

    try:
        columns = await _apply_on_panel(account, panel, quote)
        if not await ResellerAccountCRUD().update_account(account.code, **columns):
            raise RuntimeError("account update failed")
    except Exception as exc:
        refund_balance = await update_Money(user_id=telegram_id, Money=quote.total)
        log.warning(
            "reseller addon rolled back account=%s addon=%s user=%s refund_balance=%s error=%s",
            account.code,
            addon,
            telegram_id,
            refund_balance,
            exc,
        )
        return False, f"خرید {ADDON_LABELS[addon]} ناموفق بود و مبلغ به کیف پول برگشت.", quote

    event, line = {
        ADDON_DAYS: (EVENT_EXTRA_DAYS, f"📅 <b>روز اضافه:</b> <code>{quantity}</code>"),
        ADDON_VOLUME: (EVENT_EXTRA_VOLUME, f"📦 <b>حجم اضافه:</b> {format_size(gigabytes_to_bytes(quantity))}"),
        ADDON_USERS: (EVENT_CAPACITY, f"👥 <b>یوزر اضافه:</b> <code>{quantity}</code>"),
    }[addon]
    await send_reseller_log(
        f"🧩 خرید {ADDON_LABELS[addon]}",
        account=account,
        actor_id=actor_id or telegram_id,
        extra_lines=[line, f"💸 <b>مبلغ:</b> <code>{quote.total:,}</code> تومان", f"📍 <b>از:</b> {source}"],
        event=event,
        data={
            "amount": quote.total,
            "quantity": quantity,
            "before": quote.before,
            "after": quote.after,
            **({"limit_before": quote.before, "limit_after": quote.after} if addon == ADDON_USERS else {}),
        },
    )
    done = {
        ADDON_DAYS: f"✅ {quantity} روز به اعتبار نمایندگی اضافه شد.",
        ADDON_VOLUME: f"✅ {format_size(gigabytes_to_bytes(quantity))} به حجم نمایندگی اضافه شد.",
        ADDON_USERS: f"✅ سقف یوزر به {quote.after} رسید.",
    }[addon]
    return True, f"{done}\n💸 مبلغ کسر شده: {quote.total:,} تومان", quote

"""Reseller purchase: create the panel admin, debit the wallet and store the account.

Shared by the bot, direct-pay fulfillment and the user web app; callers render the outcome.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from httpx import HTTPStatusError

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, debit_Money_if_sufficient, update_Money
from app.logger import get_logger
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    pricing_mode_label,
    requires_volume_input,
    requires_wallet_for_purchase,
    validate_volume,
)
from app.services.panels.admins import (
    admin_username_exists,
    build_admin_create_payload,
    compute_reseller_data_limit,
    compute_reseller_expiration,
    create_reseller_admin,
    generate_admin_password,
    remove_reseller_admin,
)
from app.services.panels.settings import get_panel_login_url, panel_reseller_sale_enabled
from app.services.reseller.logging import EVENT_PURCHASE, send_reseller_log
from app.utils.formatting.dates import Time_Date
from app.utils.security.crypto import encrypt_data

log = get_logger(__name__)

# Error codes returned in ``PurchaseOutcome.error`` (also used as the bot's result string).
ERR_MISSING_CONTEXT = "missing_context"
ERR_PLAN_UNAVAILABLE = "plan_unavailable"
ERR_INVALID_VOLUME = "invalid_volume"
ERR_PANEL_NOT_FOUND = "panel_not_found"
ERR_USERNAME_EXISTS = "username_exists"
ERR_DISCOUNT_UNAVAILABLE = "discount_unavailable"
ERR_INSUFFICIENT_BALANCE = "insufficient_balance"
ERR_PANEL_CREATE_FAILED = "panel_create_failed"
ERR_ACCOUNT_INSERT_FAILED = "account_insert_failed"


@dataclass
class PurchaseOutcome:
    ok: bool
    error: str = ""
    message: str = ""
    account: object | None = None
    account_code: int | None = None
    password: str | None = None
    panel_url: str | None = None
    new_balance: int | None = None
    data_limit: int = 0
    volume: float | None = None
    plan: object | None = None


@dataclass
class PriceQuote:
    base_price: int
    final_price: int
    discount_percent: int = 0
    discount_code: str | None = None


@dataclass
class PurchaseQuote:
    """A validated, priced purchase; ``wallet_error`` is set when the minimum wallet rule blocks it."""

    panel: object
    plan: object
    volume: float | None
    price: PriceQuote
    wallet_error: str | None = None


async def reseller_sale_open(settings=None) -> bool:
    """Reseller sales need both the global sale switch and the reseller switch."""
    settings = settings if settings is not None else await SettingsManager().get_settings()
    return bool(settings and settings.sale_mode and settings.reseller_sale_mode)


async def apply_reseller_discount(
    user_id: int, base_price: int, code: str | None
) -> tuple[PriceQuote | None, str | None]:
    """Price after an optional discount code. Returns (quote, error)."""
    code = (code or "").strip().upper()
    if not code:
        return PriceQuote(base_price=base_price, final_price=base_price), None
    status, result = await DiscountCodeManager().validate_discount_code(code=code, user_id=user_id)
    if not status:
        return None, str(result) if result else "کد تخفیف نامعتبر است."
    percent = float(getattr(result, "discount_percentage", 0) or 0)
    final_price = max(0, int(base_price - base_price * percent / 100))
    return PriceQuote(base_price, final_price, int(percent), result.code), None


async def quote_reseller_purchase(
    user_id: int,
    *,
    panel_code: int,
    plan_id: int,
    volume: float | None = None,
    discount_code: str | None = None,
) -> tuple[PurchaseQuote | None, str | None]:
    """Validate a purchase the way the bot's flow does and price it on the server. Returns (quote, error)."""
    if not await reseller_sale_open():
        return None, "فروش نمایندگی در حال حاضر غیرفعال است."
    panel = await PanelsManager().get_panel_by_code(code=int(panel_code))
    if not panel or not panel_reseller_sale_enabled(panel):
        return None, "این پنل برای فروش نمایندگی فعال نیست."
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not plan.enable or int(plan.panel_code) != int(panel_code):
        return None, "پلن یافت نشد."

    if requires_volume_input(plan):
        if volume is None:
            return None, "حجم را وارد کنید."
        ok, error = validate_volume(plan, float(volume))
        if not ok:
            return None, error
    else:
        volume = None

    if discount_code and plan.pricing_mode != "fixed":
        return None, "کد تخفیف فقط برای پلن ثابت است."
    price, error = await apply_reseller_discount(user_id, calculate_purchase_price(plan, volume), discount_code)
    if error:
        return None, error
    return PurchaseQuote(panel, plan, volume, price, await min_wallet_error(plan, user_id)), None


def build_initial_billing_state(amount: int) -> dict:
    now = Time_Date()["stamp"]
    return {"started_at": now, "last_billed_at": now, "setup_fee": amount, "total_billed": 0}


async def min_wallet_error(plan, user_id: int) -> str | None:
    """Hourly/usage plans need a minimum wallet balance before purchase; None when satisfied."""
    if not requires_wallet_for_purchase(plan):
        return None
    settings = await SettingsManager().get_settings()
    if not settings:
        return None
    user = await UserCRUD().read_user(user_id)
    min_balance = int(settings.reseller_min_wallet_balance or 0)
    if user and user.amount < min_balance:
        return f"برای نمایندگی {pricing_mode_label(plan.pricing_mode)} حداقل موجودی {min_balance:,} تومان لازم است."
    return None


async def purchase_reseller_account(
    user_id: int,
    *,
    plan_id,
    panel_code,
    username: str | None,
    volume: float | None,
    amount: int,
    discount_code: str | None = None,
) -> PurchaseOutcome:
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not panel_code or not username:
        return PurchaseOutcome(False, ERR_MISSING_CONTEXT, "خطا: اطلاعات خرید ناقص است.")
    if not plan.enable or int(plan.panel_code) != int(panel_code):
        return PurchaseOutcome(False, ERR_PLAN_UNAVAILABLE, "این پلن دیگر برای این پنل در دسترس نیست.")

    if volume is not None:
        ok, err = validate_volume(plan, volume)
        if not ok:
            return PurchaseOutcome(False, ERR_INVALID_VOLUME, err)

    panel = await PanelsManager().get_panel_by_code(code=int(panel_code))
    if not panel:
        return PurchaseOutcome(False, ERR_PANEL_NOT_FOUND, "پنل یافت نشد.")

    if await admin_username_exists(panel, username):
        return PurchaseOutcome(False, ERR_USERNAME_EXISTS, "این نام کاربری ادمین در پنل وجود دارد.")

    password = generate_admin_password(username=username)
    data_limit = compute_reseller_data_limit(plan, volume)
    admin_payload = build_admin_create_payload(
        plan,
        username=username,
        password=password,
        telegram_id=user_id,
        data_limit=data_limit,
        max_users=plan.max_users,
    )

    if discount_code and not await DiscountCodeManager().claim_discount_use(discount_code, user_id):
        return PurchaseOutcome(False, ERR_DISCOUNT_UNAVAILABLE, "ظرفیت استفاده از این کد تخفیف تمام شده است.")

    new_balance = await debit_Money_if_sufficient(user_id=user_id, amount=int(amount))
    if new_balance is None:
        if discount_code:
            await DiscountCodeManager().release_discount_use(discount_code)
        return PurchaseOutcome(False, ERR_INSUFFICIENT_BALANCE, "‼️ موجودی کیف پول شما کافی نیست.")

    start_time = time.time()
    try:
        created = await create_reseller_admin(panel, admin_payload)
    except Exception as e:
        await update_Money(user_id=user_id, Money=int(amount))
        if discount_code:
            await DiscountCodeManager().release_discount_use(discount_code)
        if not isinstance(e, HTTPStatusError):
            raise
        log.error("create_reseller_admin failed: %s", e.response.text)
        return PurchaseOutcome(False, ERR_PANEL_CREATE_FAILED, "خطا در ساخت ادمین پنل. لطفاً با پشتیبانی تماس بگیرید.")

    account_code = await ResellerAccountCRUD().generate_unique_code()
    created_ok, created_err = await ResellerAccountCRUD().create_account(
        code=account_code,
        telegram_id=user_id,
        panel_code=int(panel_code),
        panel_admin_id=getattr(created, "id", None),
        username=username,
        password_encrypted=encrypt_data(password),
        plan_id=plan.id,
        pricing_mode=plan.pricing_mode,
        data_limit=data_limit or None,
        max_users=plan.max_users or None,
        purchased_volume=volume,
        createtime=Time_Date()["stamp"],
        expiration_time=compute_reseller_expiration(plan),
        status="active",
        billing_state=json.dumps(build_initial_billing_state(amount), ensure_ascii=False),
    )
    if not created_ok:
        # Without a DB row nothing can bill, renew or clean up this admin: undo everything.
        log.error("reseller account insert failed user=%s username=%s: %s", user_id, username, created_err)
        try:
            await remove_reseller_admin(panel, created.id)
        except Exception as exc:
            log.error("rollback remove admin failed username=%s: %s", username, exc)
        await update_Money(user_id=user_id, Money=int(amount))
        if discount_code:
            await DiscountCodeManager().release_discount_use(discount_code)
        return PurchaseOutcome(
            False, ERR_ACCOUNT_INSERT_FAILED, "خطا در ثبت نمایندگی. مبلغ به کیف پول برگشت؛ لطفاً دوباره تلاش کنید."
        )

    ok, account = await ResellerAccountCRUD().get_account(account_code)
    extra = [
        f"💸 <b>مبلغ:</b> <code>{int(amount):,}</code> تومان",
        f"⏱ <b>زمان ساخت:</b> <code>{time.time() - start_time:.2f}</code> ثانیه",
    ]
    if discount_code:
        extra.append(f"🎟 <b>کد تخفیف:</b> <code>{discount_code}</code>")
    await send_reseller_log(
        "📢 خرید نمایندگی جدید",
        account=account if ok else None,
        actor_id=user_id,
        event=EVENT_PURCHASE,
        telegram_id=user_id,
        data={
            "amount": int(amount),
            "plan_id": plan.id,
            "pricing_mode": plan.pricing_mode,
            "volume": volume,
            "discount_code": discount_code,
        },
        extra_lines=extra
        if ok
        else [
            f"👤 <b>کاربر:</b> <code>{user_id}</code>",
            f"🎫 <b>کد:</b> <code>{account_code}</code>",
            f"🏢 <b>یوزر ادمین:</b> <code>{username}</code>",
            f"📛 <b>پنل:</b> <code>{panel_code}</code>",
            *extra,
        ],
    )
    return PurchaseOutcome(
        True,
        account=account if ok else None,
        account_code=account_code,
        password=password,
        panel_url=get_panel_login_url(panel),
        new_balance=new_balance,
        data_limit=data_limit,
        volume=volume,
        plan=plan,
    )

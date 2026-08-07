"""Reseller account renewal and limit extension."""

from __future__ import annotations

from pasarguard import AdminModify

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD, debit_Money_if_sufficient, update_Money
from app.logger import get_logger
from app.services.billing.reseller_pricing import calculate_purchase_price
from app.services.panels.admins import (
    activate_reseller_admin,
    compute_reseller_data_limit,
    get_reseller_admin,
    modify_reseller_admin,
)
from app.services.reseller.logging import send_reseller_log
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size

log = get_logger(__name__)


async def renew_reseller_account(
    account_code: int,
    plan_id: int,
    telegram_id: int,
    *,
    amount: int | None = None,
    discount_code: str | None = None,
    actor_id: int | None = None,
    actor_role: str | None = None,
) -> tuple[bool, str]:
    ok, account_or_msg = await ResellerAccountCRUD().get_account(account_code)
    if not ok:
        return False, str(account_or_msg)
    account = account_or_msg
    if account.telegram_id != telegram_id:
        return False, "این نمایندگی متعلق به شما نیست."

    if account.pricing_mode != "fixed":
        return False, "تمدید فقط برای پلن‌های ثابت امکان‌پذیر است."

    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not plan.enable:
        return False, "پلن تمدید یافت نشد."
    if plan.pricing_mode != "fixed":
        return False, "فقط پلن‌های ثابت برای تمدید قابل انتخاب هستند."
    if plan.panel_code != account.panel_code:
        return False, "این پلن متعلق به پنل نمایندگی شما نیست."

    charge = int(amount if amount is not None else calculate_purchase_price(plan))
    if charge <= 0:
        return False, "قیمت پلن نامعتبر است."

    if discount_code:
        status, validation = await DiscountCodeManager().validate_discount_code(code=discount_code, user_id=telegram_id)
        if not status:
            return False, str(validation)

    user = await UserCRUD().read_user(user_id=telegram_id)
    if user is None:
        return False, "کاربر یافت نشد."
    if user.amount < charge:
        return False, f"موجودی کافی نیست. نیاز: {charge:,} تومان"

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    current = await get_reseller_admin(panel, account.username)
    if not current:
        return False, "ادمین در پنل یافت نشد."

    added_bytes = compute_reseller_data_limit(plan, account.purchased_volume)
    current_limit = int(getattr(current, "data_limit", 0) or 0)
    new_panel_limit = current_limit + added_bytes if added_bytes > 0 else current_limit
    modify_kwargs: dict = {}
    if added_bytes > 0:
        modify_kwargs["data_limit"] = new_panel_limit

    if plan.duration and plan.duration > 0:
        base = int(account.expiration_time or Time_Date()["stamp"])
        account_expire = max(base, Time_Date()["stamp"]) + (int(plan.duration) * 86400)
    else:
        account_expire = account.expiration_time

    # Debit first (atomic), then mutate panel/DB; refund on failure.
    new_balance = await debit_Money_if_sufficient(user_id=telegram_id, amount=charge)
    if new_balance is None:
        return False, f"موجودی کافی نیست. نیاز: {charge:,} تومان"

    try:
        if modify_kwargs:
            await modify_reseller_admin(panel, account.username, AdminModify(**modify_kwargs))

        try:
            await activate_reseller_admin(panel, account.username)
        except Exception as exc:
            log.warning("renew activate admin failed code=%s: %s", account.code, exc)

        new_account_limit = (account.data_limit or 0) + added_bytes if added_bytes > 0 else account.data_limit
        await ResellerAccountCRUD().update_account(
            account.code,
            plan_id=plan.id,
            expiration_time=account_expire,
            data_limit=new_account_limit,
            status="active",
        )

        if discount_code:
            await DiscountCodeManager().update_discount_usage(code=discount_code)
    except Exception as exc:
        refund_balance = await update_Money(user_id=telegram_id, Money=charge)
        log.warning(
            "Reseller renewal rolled back balance account=%s user=%s refund_balance=%s error=%s",
            account.code,
            telegram_id,
            refund_balance,
            exc,
        )
        return False, "تمدید ناموفق بود و مبلغ به کیف پول برگشت."

    ok, refreshed = await ResellerAccountCRUD().get_account(account.code)
    renewed_account = refreshed if ok else account
    extra = [f"💸 <b>مبلغ:</b> <code>{charge:,}</code> تومان"]
    if added_bytes > 0:
        extra.append(f"📦 <b>حجم اضافه‌شده:</b> {format_size(added_bytes)}")
    if plan.duration:
        extra.append(f"⏰ <b>روز اضافه‌شده:</b> <code>{plan.duration}</code>")
    if discount_code:
        extra.append(f"🎟 <b>کد تخفیف:</b> <code>{discount_code}</code>")
    await send_reseller_log(
        "💎 تمدید نمایندگی",
        account=renewed_account,
        actor_id=actor_id or telegram_id,
        actor_role=actor_role,
        extra_lines=extra,
    )
    success = f"نمایندگی با موفقیت تمدید شد. مبلغ {charge:,} تومان کسر شد."
    if added_bytes > 0:
        success += f"\n📊 حجم اضافه‌شده: {format_size(added_bytes)}"
    if plan.duration:
        success += f"\n⏰ {plan.duration} روز به مدت اعتبار اضافه شد."
    return True, success

"""Extra reseller user-capacity purchase (independent of plan/pricing mode)."""

from __future__ import annotations

from pasarguard import AdminModify, RoleLimits

from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.user import debit_Money_if_sufficient, update_Money
from app.logger import get_logger
from app.services.panels.admins import get_reseller_admin, modify_reseller_admin
from app.services.panels.settings import is_reseller_capacity_ready, panel_reseller_capacity_settings
from app.services.reseller.logging import send_reseller_log

log = get_logger(__name__)

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


def calculate_capacity_price(panel, quantity: int, *, price_per_user: int | None = None) -> int:
    """Total price for ``quantity`` extra users.

    Pass ``price_per_user`` when the caller already read ``panel_reseller_capacity_settings(panel)``
    (e.g. to display it) to avoid rebuilding the settings dict a second time; otherwise it's read live.
    """
    if price_per_user is None:
        price_per_user = panel_reseller_capacity_settings(panel)["price_per_user"]
    return int(price_per_user) * int(quantity)


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
    """Debit wallet, push new max_users to the panel, bump DB, and log.

    Caller must hold a per-user lock (``acquire_user_lock``) around this call — that lock is the
    guard against double-submission/duplicate taps; there is no separate persisted ledger.
    """
    settings = panel_reseller_capacity_settings(panel)
    if not is_reseller_capacity_ready(settings):
        return False, "خرید ظرفیت کاربر برای این پنل فعال نیست."
    if quantity <= 0:
        return False, "تعداد نامعتبر است."

    price_per_user = int(settings["price_per_user"])
    total_amount = calculate_capacity_price(panel, quantity, price_per_user=price_per_user)
    limit_before = int(account.max_users or 0)

    new_balance = await debit_Money_if_sufficient(user_id=telegram_id, amount=total_amount)
    if new_balance is None:
        return False, f"موجودی کافی نیست. نیاز: {total_amount:,} تومان"

    limit_after = limit_before + quantity
    try:
        current = await get_reseller_admin(panel, account.username)
        if not current:
            raise RuntimeError("admin not found on panel")
        overrides = current.permission_overrides
        if overrides is not None:
            overrides = overrides.model_copy(update={"max_users": limit_after})
        else:
            overrides = RoleLimits(max_users=limit_after)
        await modify_reseller_admin(panel, account.username, AdminModify(permission_overrides=overrides))

        await ResellerAccountCRUD().update_account(account.code, max_users=limit_after)
    except Exception as exc:
        refund_balance = await update_Money(user_id=telegram_id, Money=total_amount)
        log.warning(
            "Reseller capacity purchase rolled back account=%s user=%s refund_balance=%s error=%s",
            account.code,
            telegram_id,
            refund_balance,
            exc,
        )
        return False, "خرید ظرفیت ناموفق بود و مبلغ به کیف پول برگشت."

    await send_reseller_log(
        "👥 خرید ظرفیت کاربر اضافه",
        account=account,
        actor_id=actor_id or telegram_id,
        actor_role=actor_role,
        extra_lines=[
            f"💸 <b>مبلغ:</b> <code>{total_amount:,}</code> تومان",
            f"👥 <b>تعداد خریداری‌شده:</b> <code>{quantity}</code> ({source})",
            f"📉 <b>User Limit قبل:</b> <code>{limit_before}</code>",
            f"📈 <b>User Limit بعد:</b> <code>{limit_after}</code>",
        ],
    )

    success = (
        f"✅ خرید ظرفیت با موفقیت انجام شد.\n"
        f"👥 تعداد خریداری‌شده: {quantity}\n"
        f"📊 User Limit جدید: {limit_after}\n"
        f"💸 مبلغ کسر شده: {total_amount:,} تومان"
    )
    return True, success

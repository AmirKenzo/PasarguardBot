"""Proactive low-balance warning for pay-as-you-go (hourly/usage) reseller accounts.

Runs ahead of the billing job's reactive suspend in ``billing.py`` — this only
notifies, it never charges or suspends. Warned state persists in each account's
``billing_state`` JSON (mirrors ``last_billed_at``/``total_billed`` there) so we
don't need a schema migration for a single boolean flag.
"""

import time

from app import Kenzo
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.logger import LogTag, get_logger
from app.services.reseller.logging import send_reseller_log

logger = get_logger(__name__)

# Wallet balance (Toman) below which a reseller is warned their PAYG accounts risk suspension.
LOW_BALANCE_WARNING_TOMAN = 100_000
_BILLABLE_MODES = ("hourly", "usage")


async def _notify_user(telegram_id: int, text: str) -> bool:
    try:
        await Kenzo.send_message(telegram_id, text, parse_mode="markdown")
        return True
    except Exception as exc:
        logger.warning("reseller low-balance notify failed user=%s: %s", telegram_id, exc)
        return False


def _group_by_user(accounts) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for account in accounts:
        grouped.setdefault(account.telegram_id, []).append(account)
    return grouped


async def run_reseller_low_balance_warning() -> None:
    """Warn resellers once when their wallet drops below the threshold; clear the flag on top-up."""
    start_time = time.time()
    logger.debug("%s reseller_low_balance_warning started", LogTag.JOB)

    settings = await SettingsManager().get_settings()
    if not settings or not settings.reseller_sale_mode:
        logger.debug("%s reseller_low_balance_warning skipped (reseller_sale_mode off)", LogTag.JOB)
        return

    account_crud = ResellerAccountCRUD()
    accounts = await account_crud.get_billable_accounts(_BILLABLE_MODES)
    if not accounts:
        return

    user_crud = UserCRUD()
    warned = 0
    cleared = 0

    for telegram_id, user_accounts in _group_by_user(accounts).items():
        user = await user_crud.read_user(telegram_id)
        balance = user.amount if user else 0
        already_notified = any(
            ResellerAccountCRUD.load_billing_state(account.billing_state).get("low_balance_notified")
            for account in user_accounts
        )

        if balance < LOW_BALANCE_WARNING_TOMAN:
            if already_notified:
                continue
            usernames = "، ".join(f"`{account.username}`" for account in user_accounts)
            sent = await _notify_user(
                telegram_id,
                "⚠️ **موجودی کیف پول شما رو به اتمام است**\n\n"
                f"💳 موجودی فعلی: `{balance:,}` تومان\n"
                f"🏢 نمایندگی‌های مصرفی (Pay as you go): {usernames}\n\n"
                "در صورتی که موجودی خود را افزایش ندهید، این پنل‌ها به‌محض ناکافی شدن موجودی "
                "به‌صورت خودکار غیرفعال خواهند شد.\n"
                "برای جلوگیری از قطعی، لطفاً کیف پول خود را شارژ کنید.",
            )
            if not sent:
                continue
            warned += 1
            for account in user_accounts:
                state = ResellerAccountCRUD.load_billing_state(account.billing_state)
                state["low_balance_notified"] = True
                await account_crud.update_account(
                    account.code, billing_state=ResellerAccountCRUD.dump_billing_state(state)
                )
            await send_reseller_log(
                "⚠️ هشدار پایین بودن موجودی",
                extra_lines=[
                    f"👤 <b>کاربر:</b> <code>{telegram_id}</code>",
                    f"💳 <b>موجودی:</b> <code>{balance:,}</code> تومان",
                    f"🏢 <b>نمایندگی‌ها:</b> {', '.join(account.username for account in user_accounts)}",
                ],
            )
        elif already_notified:
            cleared += 1
            for account in user_accounts:
                state = ResellerAccountCRUD.load_billing_state(account.billing_state)
                if state.pop("low_balance_notified", None) is not None:
                    await account_crud.update_account(
                        account.code, billing_state=ResellerAccountCRUD.dump_billing_state(state)
                    )

    elapsed = time.time() - start_time
    logger.info(
        f"{LogTag.JOB} reseller_low_balance_warning | duration={elapsed:.2f}s, "
        f"accounts={len(accounts)}, warned={warned}, cleared={cleared}"
    )

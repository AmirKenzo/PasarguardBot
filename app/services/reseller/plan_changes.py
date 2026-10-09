"""Tell pay-as-you-go resellers when the live rate of their plan changes.

Hourly and usage accounts are billed at the plan's current ``unit_price`` (no purchase-time
snapshot), so a price edit changes what they pay from the next billing tick.
"""

from __future__ import annotations

from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_events import ResellerEventCRUD
from app.logger import get_logger
from app.services.reseller.logging import EVENT_PRICE_CHANGE, send_reseller_log
from app.services.send_queue import enqueue

log = get_logger(__name__)

LIVE_RATE_MODES = ("hourly", "usage")
RATE_UNITS = {"hourly": "تومان در ساعت", "usage": "تومان به ازای هر گیگابایت"}


async def notify_plan_rate_change(plan, *, old_rate: float, new_rate: float, actor_id: int | None = None) -> int:
    """Message every user with a live account on ``plan``. Returns the number of users notified."""
    if plan.pricing_mode not in LIVE_RATE_MODES or int(old_rate) == int(new_rate):
        return 0
    accounts = [
        account
        for account in await ResellerAccountCRUD().get_accounts_by_plan(plan.id)
        if account.status != "expired" and account.pricing_mode == plan.pricing_mode
    ]
    if not accounts:
        return 0

    unit = RATE_UNITS[plan.pricing_mode]
    direction = "افزایش" if new_rate > old_rate else "کاهش"
    data = {"plan_id": plan.id, "old_rate": int(old_rate), "new_rate": int(new_rate)}
    by_user: dict[int, list] = {}
    for account in accounts:
        by_user.setdefault(account.telegram_id, []).append(account)
        await ResellerEventCRUD().add_event(
            kind=EVENT_PRICE_CHANGE,
            title=f"💲 {direction} نرخ پلن",
            account_code=account.code,
            telegram_id=account.telegram_id,
            actor_id=actor_id,
            actor_role="ادمین",
            data=data,
        )

    notified = 0
    for telegram_id, user_accounts in by_user.items():
        usernames = "، ".join(f"`{account.username}`" for account in user_accounts)
        text = (
            f"💲 **{direction} نرخ پلن نمایندگی**\n\n"
            f"🏢 نمایندگی‌ها: {usernames}\n"
            f"📉 نرخ قبلی: `{int(old_rate):,}` {unit}\n"
            f"📈 نرخ جدید: `{int(new_rate):,}` {unit}\n\n"
            "از دوره‌ی بعدی صورت‌حساب، کسر از کیف پول با نرخ جدید انجام می‌شود."
        )
        try:
            if await enqueue(text, entity=telegram_id, parse_mode="markdown"):
                notified += 1
        except Exception as exc:
            log.warning("plan rate notify failed user=%s plan=%s: %s", telegram_id, plan.id, exc)

    await send_reseller_log(
        f"💲 {direction} نرخ پلن نمایندگی #{plan.id}",
        actor_id=actor_id,
        actor_role="ادمین",
        extra_lines=[
            f"📉 <b>قبلی:</b> <code>{int(old_rate):,}</code> {unit}",
            f"📈 <b>جدید:</b> <code>{int(new_rate):,}</code> {unit}",
            f"🏢 <b>نمایندگی‌های متصل:</b> <code>{len(accounts)}</code>",
            f"📨 <b>کاربران مطلع‌شده:</b> <code>{notified}</code>",
        ],
    )
    return notified

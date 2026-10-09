"""Reseller activity: one call records the event in the DB and posts it to the log channel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_events import ResellerEventCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.logger import LogType, get_logger
from app.services.billing.reseller_pricing import pricing_mode_label
from app.telegram.shared.utils.logging import send_log_message
from app.utils.formatting.dates import timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size

if TYPE_CHECKING:
    from app.db.models.reseller_accounts import ResellerAccount

log = get_logger(__name__)

# ``reseller_events.kind`` values; the web app and admin panel label/filter by these.
EVENT_PURCHASE = "purchase"
EVENT_IMPORT = "import"
EVENT_RENEW = "renew"
EVENT_CAPACITY = "capacity"
EVENT_PAUSE = "pause"
EVENT_RESUME = "resume"
EVENT_ADMIN_PAUSE = "admin_pause"
EVENT_ADMIN_RESUME = "admin_resume"
EVENT_SUSPEND = "suspend"
EVENT_REACTIVATE = "reactivate"
EVENT_USAGE_CAP_SET = "usage_cap_set"
EVENT_USAGE_CAP_HIT = "usage_cap_hit"
EVENT_PASSWORD = "password"
EVENT_LOW_BALANCE = "low_balance"
EVENT_EXPIRE = "expire"
EVENT_PURGE = "purge"
EVENT_DELETE = "delete"


async def _account_context_lines(account: ResellerAccount) -> list[str]:
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    panel_name = panel.name if panel else "—"
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None

    lines = [
        f"👤 <b>کاربر:</b> <code>{account.telegram_id}</code>",
        f"🎫 <b>کد نمایندگی:</b> <code>{account.code}</code>",
        f"🏢 <b>یوزر ادمین:</b> <code>{account.username}</code>",
        f"📛 <b>پنل:</b> {panel_name} (<code>{account.panel_code}</code>)",
        f"📋 <b>نوع پلن:</b> {pricing_mode_label(account.pricing_mode)}",
        f"📊 <b>وضعیت:</b> <code>{account.status}</code>",
    ]
    if plan:
        lines.append(f"📦 <b>پلن:</b> #{plan.id}")
    if account.purchased_volume:
        lines.append(f"📦 <b>حجم خرید:</b> {account.purchased_volume:g}")
    if account.data_limit:
        lines.append(f"📥 <b>سقف ترافیک:</b> {format_size(account.data_limit)}")
    if account.max_users:
        lines.append(f"👥 <b>سقف یوزر:</b> {account.max_users}")
    if account.expiration_time:
        lines.append(f"⏰ <b>انقضا:</b> {timestamp_to_persian_expiry(account.expiration_time)}")
    return lines


async def send_reseller_log(
    title: str,
    *,
    account: ResellerAccount | None = None,
    actor_id: int | None = None,
    actor_role: str | None = None,
    extra_lines: list[str] | None = None,
    event: str | None = None,
    data: dict[str, Any] | None = None,
    telegram_id: int | None = None,
) -> None:
    """Post ``title`` to the reseller log channel and, when ``event`` is set, store it in history.

    ``data`` is the structured payload (amounts, reasons, ...) the web pages render;
    ``telegram_id`` scopes an account-less event (e.g. a low-balance warning) to its user.
    """
    if event:
        await ResellerEventCRUD().add_event(
            kind=event,
            title=title,
            account_code=account.code if account is not None else None,
            telegram_id=account.telegram_id if account is not None else telegram_id,
            actor_id=actor_id,
            actor_role=actor_role,
            data=data,
        )

    parts = [f"<b>{title}</b>", ""]
    if actor_id is not None:
        role = actor_role or "کاربر"
        parts.append(f"👮 <b>انجام‌دهنده:</b> <code>{actor_id}</code> ({role})")
        parts.append("")
    if account is not None:
        parts.extend(await _account_context_lines(account))
        parts.append("")
    if extra_lines:
        parts.extend(line for line in extra_lines if line)

    message = "\n".join(parts).strip()
    await send_log_message(LogType.RESELLER, message=message, parse_mode="html")

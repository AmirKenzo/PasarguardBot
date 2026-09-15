"""Public, filtered cards for a channel customers can see.

These are not the admin logs. An admin log names the buyer and carries the
config links, so it belongs in a private channel; these hide most of the user's
id, carry no links, and end in a button back to the bot — the kind of post a
shop pins in its public channel as evidence that it is trading.

Each kind is opt-in on its own: nothing is sent until an admin points that
report type at a destination, because the send queue would otherwise fall back
to the admin log channel and repeat what is already there.

Every template is admin-editable, and the values are escaped before they reach
it, so a customer cannot smuggle markup into the channel through a config name.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from telethon import Button

from app import Kenzo
from app.db.crud.bot_texts import BotTextCRUD
from app.db.crud.log_channels import LogChannelManager
from app.logger import LogType, get_logger
from app.services.send_queue import enqueue
from app.utils.formatting import Time_Date

logger = get_logger(__name__)

BUTTON_LABEL = "🛒 خرید از ربات"
VISIBLE_ID_DIGITS = 5


def _card(title: str, tag: str, lines: tuple[str, ...]) -> str:
    """One heading, each field in its own quote block, then the timestamp."""
    quoted = "\n".join(f"<blockquote>{line}</blockquote>" for line in lines)
    return f"✅ <b>{title}</b> {tag}\n{quoted}\n📅 {{date}} — ⏰ {{time}}"


@dataclass(frozen=True)
class PublicReportKind:
    """One card: where it goes, which text key edits it, what it says by default."""

    log_type: LogType
    text_key: str
    template: str


PURCHASE = PublicReportKind(
    LogType.PURCHASE,
    "purchase_report_message",
    _card(
        "گزارش خرید",
        "#سفارش_جدید",
        (
            "👤 آیدی کاربر : {user}",
            "🖥 پنل : {panel}",
            "🏷 دسته‌بندی : {plan}",
            "📦 سرویس : {service}",
            "💰 مبلغ پرداختی : {price} تومان",
        ),
    ),
)

RENEW = PublicReportKind(
    LogType.RENEW,
    "renew_report_message",
    _card(
        "گزارش تمدید",
        "#تمدید_جدید",
        (
            "👤 آیدی کاربر : {user}",
            "🖥 پنل : {panel}",
            "🏷 دسته‌بندی : {plan}",
            "💰 مبلغ پرداختی : {price} تومان",
        ),
    ),
)

TRIAL = PublicReportKind(
    LogType.TRIAL,
    "trial_report_message",
    _card(
        "گزارش سرویس تست",
        "#تست_جدید",
        (
            "👤 آیدی کاربر : {user}",
            "🖥 پنل : {panel}",
            "📥 حجم : {plan}",
            "⏰ مدت : {service}",
        ),
    ),
)

_bot_username: str | None = None
_bot_username_looked_up = False


def mask_user_id(user_id: int | str) -> str:
    """Keep the leading digits and hide the rest, as 56943***** ."""
    digits = str(user_id)
    visible = min(VISIBLE_ID_DIGITS, max(len(digits) - 1, 0))
    return digits[:visible] + "*" * (len(digits) - visible)


async def _buy_button() -> list[list[Button]] | None:
    """A link back to the bot, resolved once and remembered."""
    global _bot_username, _bot_username_looked_up
    if not _bot_username_looked_up:
        _bot_username_looked_up = True
        try:
            me = await Kenzo.get_me()
            _bot_username = getattr(me, "username", None)
        except Exception as exc:
            logger.warning("Could not resolve the bot username for the public report: %s", exc)
    if not _bot_username:
        return None
    return [[Button.url(BUTTON_LABEL, f"https://t.me/{_bot_username}")]]


async def send_public_report(
    kind: PublicReportKind,
    *,
    user_id: int,
    panel_name: str | None = None,
    plan_label: str | None = None,
    service_label: str | None = None,
    price: int | None = None,
) -> None:
    """Post one card, if an admin has given that report type a home."""
    try:
        destination = await LogChannelManager().get_log_channel_destination(kind.log_type.value)
        if not destination:
            return

        stamp = Time_Date()
        template = await BotTextCRUD().get_text(kind.text_key) or kind.template
        values = {
            "{user}": mask_user_id(user_id),
            "{panel}": panel_name or "—",
            "{plan}": plan_label or "—",
            "{service}": service_label or "—",
            "{price}": f"{int(price):,}" if price is not None else "—",
            "{date}": stamp["j"],
            "{time}": stamp["jf"].split(" ", 1)[-1],
        }
        # The cards ship as HTML because the quote blocks have no markdown form,
        # but an admin who wrote their own text before that is left alone: a
        # template with no tag in it is sent the way it was written.
        as_html = "<" in template
        message = template
        for placeholder, value in values.items():
            text = str(value)
            message = message.replace(placeholder, html.escape(text) if as_html else text)

        buttons = await _buy_button()
        parse_mode = "html" if as_html else None
        await enqueue(message=message, log_type=kind.log_type, buttons=buttons, parse_mode=parse_mode)
    except Exception as exc:
        # A missing channel post must never cost the customer their purchase.
        logger.error("Failed to send the %s report: %s", kind.log_type.value, exc)


async def send_purchase_report(
    *,
    user_id: int,
    panel_name: str | None,
    plan_label: str,
    service_label: str,
    price: int,
) -> None:
    await send_public_report(
        PURCHASE,
        user_id=user_id,
        panel_name=panel_name,
        plan_label=plan_label,
        service_label=service_label,
        price=price,
    )


async def send_renew_report(
    *,
    user_id: int,
    panel_name: str | None = None,
    plan_label: str | None = None,
    price: int | None = None,
) -> None:
    await send_public_report(RENEW, user_id=user_id, panel_name=panel_name, plan_label=plan_label, price=price)


async def send_trial_report(
    *,
    user_id: int,
    panel_name: str | None = None,
    volume_label: str | None = None,
    duration_label: str | None = None,
) -> None:
    await send_public_report(
        TRIAL,
        user_id=user_id,
        panel_name=panel_name,
        plan_label=volume_label,
        service_label=duration_label,
    )

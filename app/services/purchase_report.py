"""The public "someone just bought" card for a sales channel.

This is not the purchase log admins already get: that one names the buyer and
carries the config links, so it belongs in a private channel. This card hides
most of the buyer's id, carries no links, and ends in a button back to the bot,
so it can sit in a public channel as evidence that the shop is trading.

It is opt-in. Nothing is sent until an admin points the ``purchase`` report type
at a destination, because the queue would otherwise fall back to the admin log
channel and duplicate what is already there.
"""

from __future__ import annotations

from telethon import Button

from app import Kenzo
from app.db.crud.bot_texts import BotTextCRUD
from app.db.crud.log_channels import LogChannelManager
from app.logger import LogType, get_logger
from app.services.send_queue import enqueue
from app.utils.formatting import Time_Date

logger = get_logger(__name__)

TEXT_KEY = "purchase_report_message"

DEFAULT_TEMPLATE = (
    "✅ **گزارش خرید** #سفارش_جدید\n\n"
    "👤 آیدی کاربر : `{user}`\n"
    "🖥 پنل : {panel}\n"
    "📦 دسته‌بندی : {plan}\n"
    "🎁 سرویس : {service}\n"
    "💰 مبلغ پرداختی : {price} تومان\n\n"
    "📅 {date} — ⏰ {time}"
)

BUTTON_LABEL = "🛒 خرید از ربات"
VISIBLE_ID_DIGITS = 5

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
            logger.warning("Could not resolve the bot username for the purchase report: %s", exc)
    if not _bot_username:
        return None
    return [[Button.url(BUTTON_LABEL, f"https://t.me/{_bot_username}")]]


async def send_purchase_report(
    *,
    user_id: int,
    panel_name: str | None,
    plan_label: str,
    service_label: str,
    price: int,
) -> None:
    """Post the sales card, if an admin has given the purchase report a home."""
    try:
        destination = await LogChannelManager().get_log_channel_destination(LogType.PURCHASE.value)
        if not destination:
            return

        stamp = Time_Date()
        template = await BotTextCRUD().get_text(TEXT_KEY) or DEFAULT_TEMPLATE
        message = (
            template.replace("{user}", mask_user_id(user_id))
            .replace("{panel}", panel_name or "—")
            .replace("{plan}", plan_label or "—")
            .replace("{service}", service_label or "—")
            .replace("{price}", f"{int(price):,}")
            .replace("{date}", stamp["j"])
            .replace("{time}", stamp["jf"].split(" ", 1)[-1])
        )

        buttons = await _buy_button()
        await enqueue(message=message, log_type=LogType.PURCHASE, buttons=buttons)
    except Exception as exc:
        # A missing sales post must never cost the customer their purchase.
        logger.error("Failed to send the purchase report: %s", exc)

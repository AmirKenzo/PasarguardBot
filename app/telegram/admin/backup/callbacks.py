"""Callback handlers for admin backup."""

from telethon import events

from app.db.crud.log_channels import LogChannelManager
from app.db.crud.settings import SettingsManager
from app.logger import LogType, get_logger
from app.services.backup import run_backup_and_send
from app.telegram.admin.backup import keyboards, states, texts
from app.telegram.state import set_step
from config import ADMIN_ID

logger = get_logger(__name__)

_BACKUP_CALLBACKS = frozenset({"backup_run_now", "backup_set_interval", "backup_menu"})


def _backup_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    return event.data.decode("utf-8") in _BACKUP_CALLBACKS


async def _current_interval() -> int:
    settings = await SettingsManager().get_settings()
    if not settings:
        return 24
    return max(0, int(getattr(settings, "backup_interval_hours", 24) or 0))


async def _channel_configured() -> bool:
    dest = await LogChannelManager().get_log_channel_destination(LogType.BACKUP.value)
    return dest is not None


async def _edit_menu(event: events.CallbackQuery.Event) -> None:
    hours = await _current_interval()
    await set_step(event.sender_id, states.BACKUP_STEP)
    await event.edit(
        texts.menu_text(hours, await _channel_configured()),
        buttons=keyboards.menu_buttons(hours),
        parse_mode="md",
    )


async def callback_backup(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")

    if data == "backup_menu":
        await _edit_menu(event)
        return

    if data == "backup_set_interval":
        hours = await _current_interval()
        await set_step(event.sender_id, states.SET_BACKUP_INTERVAL_STEP)
        await event.edit(
            (
                "⏱ **تنظیم فاصله بکاپ خودکار**\n\n"
                f"مقدار فعلی: `{hours}` ساعت\n"
                "عدد ساعت را ارسال کنید (مثال: `1` یا `24`).\n"
                "برای خاموش کردن بکاپ خودکار عدد `0` را بفرستید."
            ),
            buttons=keyboards.interval_prompt_buttons(),
            parse_mode="md",
        )
        return

    if data == "backup_run_now":
        if not await _channel_configured():
            await event.answer(texts.CHANNEL_NOT_SET_ALERT, alert=True)
            hours = await _current_interval()
            await event.edit(
                f"{texts.CHANNEL_NOT_SET}\n\n{texts.menu_text(hours, False)}",
                buttons=keyboards.menu_buttons(hours),
                parse_mode="md",
            )
            return

        await event.answer()
        await event.edit(texts.WORKING)
        result = await run_backup_and_send(trigger="manual")
        hours = await _current_interval()
        await event.edit(
            f"{result.message}\n\n{texts.menu_text(hours, await _channel_configured())}",
            buttons=keyboards.menu_buttons(hours),
            parse_mode="md",
        )


def register(client):
    client.add_event_handler(
        callback_backup,
        events.CallbackQuery(func=_backup_callback_filter),
    )

"""Admin bot backup: run a backup now and set the automatic backup interval."""

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.log_channels import LogChannelManager
from app.db.crud.settings import SettingsManager
from app.jobs.backup import reschedule_backup_job
from app.logger import LogType
from app.services.backup import run_backup_and_send
from app.telegram.plugins import PluginContext
from app.telegram.state import get_step, set_step
from config import ADMIN_ID

MODULE_NAME = "admin.backup"
MODULE_DESCRIPTION = "Admin database/.env backup flow"

MENU_TRIGGER = "📦 بکاپ ربات"
MENU_STEP = "BackupMenu"
INTERVAL_STEP = "SetBackupInterval"
CALLBACKS = frozenset({"backup_run_now", "backup_set_interval", "backup_menu"})
CHANNEL_NOT_SET = (
    "❌ کانال لاگ بکاپ تنظیم نشده است.\nاز مسیر «مدیریت لاگ‌ها» کانال «🗄 بکاپ ربات» را ست کنید تا بکاپ ارسال شود."
)


async def _interval_hours() -> int:
    settings = await SettingsManager().get_settings()
    if not settings:
        return 24
    return max(0, int(getattr(settings, "backup_interval_hours", 24) or 0))


async def _channel_configured() -> bool:
    return await LogChannelManager().get_log_channel_destination(LogType.BACKUP.value) is not None


def menu_text(hours: int, channel_configured: bool) -> str:
    interval = "⏸ بکاپ خودکار: خاموش" if hours <= 0 else f"⏱ فاصله خودکار: هر `{hours}` ساعت"
    channel = "✅ کانال بکاپ: تنظیم شده" if channel_configured else "❌ کانال بکاپ: تنظیم نشده (از مدیریت لاگ‌ها)"
    return (
        "🗄 **بکاپ ربات**\n\n"
        f"{interval}\n"
        f"{channel}\n\n"
        "محتوای بکاپ: `database.sql` + `.env`\n"
        "فایل به کانال لاگ «🗄 بکاپ ربات» ارسال می‌شود."
    )


def menu_buttons(hours: int) -> list:
    interval = "⏸ خودکار خاموش" if hours <= 0 else f"⏱ فاصله: هر {hours} ساعت"
    return [
        [Button.inline("🚀 بکاپ همین الان", data="backup_run_now")],
        [Button.inline(f"⚙️ تنظیم فاصله ({interval})", data="backup_set_interval")],
        [Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")],
    ]


def _back_to_menu() -> list:
    return [[Button.inline("🔙 بازگشت", data="backup_menu")]]


async def _menu(prefix: str = "") -> tuple[str, list]:
    hours = await _interval_hours()
    text = menu_text(hours, await _channel_configured())
    return (f"{prefix}\n\n{text}" if prefix else text), menu_buttons(hours)


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.sender_id in ADMIN_ID and event.data.decode() in CALLBACKS


async def backup_callback(event: events.CallbackQuery.Event) -> None:
    data = event.data.decode()

    if data == "backup_menu":
        await set_step(event.sender_id, MENU_STEP)
        text, buttons = await _menu()
    elif data == "backup_set_interval":
        await set_step(event.sender_id, INTERVAL_STEP)
        text = (
            "⏱ **تنظیم فاصله بکاپ خودکار**\n\n"
            f"مقدار فعلی: `{await _interval_hours()}` ساعت\n"
            "عدد ساعت را ارسال کنید (مثال: `1` یا `24`).\n"
            "برای خاموش کردن بکاپ خودکار عدد `0` را بفرستید."
        )
        buttons = _back_to_menu()
    elif not await _channel_configured():
        await event.answer("❌ کانال بکاپ تنظیم نشده است. ابتدا از مدیریت لاگ‌ها کانال را ست کنید.", alert=True)
        text, buttons = await _menu(CHANNEL_NOT_SET)
    else:
        await event.answer()
        await event.edit("⏳ در حال تهیه بکاپ و ارسال به کانال…")
        result = await run_backup_and_send(trigger="manual")
        text, buttons = await _menu(result.message)

    await event.edit(text, buttons=buttons, parse_mode="md")


async def _message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    return msg == MENU_TRIGGER or (bool(msg) and await get_step(event.sender_id) == INTERVAL_STEP)


async def backup_message(event: Message) -> None:
    msg = (event.message.text or "").strip()

    if msg != MENU_TRIGGER:
        if not msg.isdigit():
            await event.respond(
                "لطفاً فقط عدد صحیح ارسال کنید (مثال: 1 یا 24). عدد 0 بکاپ خودکار را خاموش می‌کند.",
                buttons=_back_to_menu(),
            )
            raise events.StopPropagation
        settings = await SettingsManager().get_settings()
        if not settings:
            await event.respond("❌ تنظیمات ربات یافت نشد.")
            raise events.StopPropagation
        hours = int(msg)
        await SettingsManager().update_setting(settings.id, backup_interval_hours=hours)
        reschedule_backup_job(hours)
        notice = "✅ بکاپ خودکار خاموش شد." if hours <= 0 else f"✅ فاصله بکاپ خودکار روی هر `{hours}` ساعت تنظیم شد."
        await event.respond(notice, parse_mode="md")

    await set_step(event.sender_id, MENU_STEP)
    text, buttons = await _menu()
    await event.respond(text, buttons=buttons, parse_mode="md")
    raise events.StopPropagation


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(backup_message, events.NewMessage(incoming=True, func=_message_filter))
    kenzo.add_event_handler(backup_callback, events.CallbackQuery(func=_callback_filter))

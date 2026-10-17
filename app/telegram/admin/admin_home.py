"""Admin home panel: /panel, the admin menu entry and the panel message."""

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.db.crud.log_channels import LogChannelManager
from app.telegram.keyboards.admin import DOCS_URL, Panel_Admin_Buttons
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.plugins import PluginContext
from app.telegram.shared.url_presets import format_admin_links_message, get_bot_username
from app.telegram.state import get_step, set_step
from app.telegram.state.store import clear_user_conversation
from config import ADMIN_ID, LOG_CHANNEL

MODULE_NAME = "admin.admin_home"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin home panel shell"

ADD_PANEL_STEPS = frozenset(
    {
        "addPanel_name",
        "AddPanel_url",
        "AddPanel_auth_type",
        "AddPanel_username",
        "AddPanel_password",
        "AddPanel_api_key",
        "AddPanel_select_group",
        "ChangePanelAuth_username",
        "ChangePanelAuth_password",
        "ChangePanelAuth_api_key",
    }
)

_SETUP_WARNING = (
    "⚠️ **تنظیمات ربات کامل نیست**\n\n"
    "برای عملکرد صحیح ربات، ابتدا مورد زیر را تنظیم کنید:\n\n"
    "**📝 مدیریت لاگ‌ها**\n"
    "هنوز کانال یا گروهی برای دریافت لاگ‌های ربات انتخاب نشده است.\n"
    "از بخش **📝 مدیریت لاگ‌ها**، مقصد ارسال لاگ‌ها را مشخص کنید."
)

_OFFICIAL_CHANNEL_URL = "https://t.me/CodeByAK"

_FREE_NOTICE = (
    "💚 **این ربات کاملا رایگان است.**\n"
    "اگر بابت آن پولی پرداخت کرده‌اید، کلاهبرداری شده‌اید؛ فروشنده را در کانال رسمی گزارش دهید:\n"
    f"📢 {_OFFICIAL_CHANNEL_URL}"
)


def _admin_home_message(user_id: int, username: str | None, *, setup_warning: str | None = None) -> str:
    user_label = username or "—"
    message = (
        f"**🌺به پنل مدیریت خوش آمدید.**\n"
        f"ایدی عددی شما: `{user_id}`\n"
        f"نام کاربری شما: @{user_label}\n"
        f"\n📚 مستندات ربات: {DOCS_URL}\n"
        f"\n{_FREE_NOTICE}\n"
    )
    if setup_warning:
        message += f"\n{setup_warning}\n"
    return message


async def send_admin_home(user_id: int, username: str | None = None) -> None:
    await set_step(user_id=user_id, step="panel")

    setup_warning = None
    if LOG_CHANNEL is None:
        channels = await LogChannelManager().get_all_log_channels()
        if not any(ch.is_active for ch in channels):
            setup_warning = _SETUP_WARNING

    await Kenzo.send_message(
        entity=user_id,
        message=_admin_home_message(user_id, username, setup_warning=setup_warning),
        buttons=Panel_Admin_Buttons,
    )


async def callback_back_to_admin_panel(event: events.CallbackQuery.Event):
    if not event.is_private:
        return
    await event.answer()
    with contextlib.suppress(Exception):
        await event.delete()
    user = await event.get_sender()
    username = user.username if user else None
    await send_admin_home(event.sender_id, username)
    raise events.StopPropagation


def _panel_command_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    return msg in {"/panel", "🔙 بازگشت به پنل"}


async def message_handler_admin_panel(event: Message):
    user_id = event.sender_id
    if await get_step(user_id) in ADD_PANEL_STEPS:
        await clear_user_conversation(user_id)
    user = await event.get_sender()
    username = user.username if user else None
    await send_admin_home(user_id, username)


async def _admin_menu_entry_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False
    msg = (event.message.text or "").strip()
    if msg == "🔗 لینک های آماده":
        return True
    menu_text = await get_button_text("bt.menu_admin_panel", "⚙️ پنل مدیریت")
    return msg in {menu_text, "⚙️ پنل مدیریت"}


async def admin_menu_entry_handler(event: Message):
    msg = (event.message.text or "").strip()
    if msg == "🔗 لینک های آماده":
        bot_username = await get_bot_username(Kenzo)
        links_message = format_admin_links_message(bot_username)
        buttons = [[Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")]]
        await event.respond(links_message, buttons=buttons, parse_mode="md")
        return

    user = await event.get_sender()
    await send_admin_home(event.sender_id, user.username if user else None)


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(
        message_handler_admin_panel,
        events.NewMessage(incoming=True, func=_panel_command_filter),
    )
    kenzo.add_event_handler(
        admin_menu_entry_handler,
        events.NewMessage(incoming=True, func=_admin_menu_entry_filter),
    )
    kenzo.add_event_handler(
        callback_back_to_admin_panel,
        events.CallbackQuery(data="back_to_admin_panel", func=lambda e: e.sender_id in ADMIN_ID),
    )

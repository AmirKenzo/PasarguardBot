"""Message handlers for admin home panel."""

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.db.crud.settings import SettingsManager
from app.services.keyboard_glass import glass_mode_active
from app.telegram.admin.admin_home.service import ADD_PANEL_STEPS, send_admin_home
from app.telegram.keyboards.admin import (
    ADMIN_SECTION_BY_LABEL,
    admin_section_inline,
    admin_section_keyboard,
)
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.shared.url_presets import format_admin_links_message, get_bot_username
from app.telegram.state import get_step
from app.telegram.state.store import clear_user_conversation
from config import ADMIN_ID


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


async def _admin_section_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    return (event.message.text or "").strip() in ADMIN_SECTION_BY_LABEL


async def admin_section_handler(event: Message):
    """Open one drawer of the admin menu."""
    section = ADMIN_SECTION_BY_LABEL[(event.message.text or "").strip()]
    setting = await SettingsManager().get_settings()
    if glass_mode_active(setting):
        await event.respond(section.label, buttons=admin_section_inline(section))
    else:
        await event.respond(section.label, buttons=admin_section_keyboard(section))
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        admin_section_handler,
        events.NewMessage(incoming=True, func=_admin_section_filter),
    )
    client.add_event_handler(
        message_handler_admin_panel,
        events.NewMessage(incoming=True, func=_panel_command_filter),
    )
    client.add_event_handler(
        admin_menu_entry_handler,
        events.NewMessage(incoming=True, func=_admin_menu_entry_filter),
    )

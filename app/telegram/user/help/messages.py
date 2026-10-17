"""Message handlers for user help."""

from __future__ import annotations

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.logger import get_logger
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.help import get_help_buttons
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.messages.message_drafts import send_message_draft
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import get_step
from app.telegram.user.start.helpers import get_user_lang
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

logger = get_logger(__name__)


async def help_menu_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) == "ban":
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False

    msg = event.message.text or event.message.message or ""
    if msg == "/help":
        return True
    menu_text = await get_button_text("bt.menu_help", "📚 راهنما")
    return msg in {menu_text, "📚 راهنما"}


@bot_is_offline
async def help_menu_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    lang = await get_user_lang(user_id)
    help_message_text = await get_bot_text(
        key="help_message",
        default=DEFAULT_BOT_TEXTS["help_message"],
        lang=lang,
    )
    await send_message_draft(
        Kenzo,
        event.chat_id,
        help_message_text,
        parse_mode=Kenzo.parse_mode,
        delay=0.1,
        logger=logger,
    )
    await Kenzo.send_message(
        entity=user_id,
        message=help_message_text,
        buttons=await get_help_buttons(user_id),
    )
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        help_menu_handler,
        events.NewMessage(incoming=True, func=help_menu_filter),
    )

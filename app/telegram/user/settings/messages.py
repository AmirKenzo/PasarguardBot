"""Message handlers for user advanced settings."""

from __future__ import annotations

from telethon import events
from telethon.tl.custom import Message

from app.db.crud.keyboards import get_button_text
from app.db.crud.user import UserCRUD
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import home_back_button
from app.telegram.keyboards.user_settings import create_buttons_user_settings
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import get_step, set_step
from app.utils.media.qrcode import create_qr_code
from app.utils.text.bot_texts import get_bot_text

BOT_LANGUAGE = "fa"


async def _user_lang(user_id: int) -> str:
    info = await UserCRUD().read_user(user_id)
    return info.language if info and info.language else BOT_LANGUAGE


async def advanced_settings_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) == "ban":
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False

    msg = event.message.text or event.message.message or ""
    menu_text = await get_button_text("bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته")
    return msg in {menu_text, "⚙️ تنظیمات پیشرفته"}


@bot_is_offline
async def advanced_settings_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    lang = await _user_lang(event.sender_id)
    is_callback = hasattr(event, "answer")
    user = await UserCRUD().read_user(event.sender_id)
    buttons = create_buttons_user_settings(user)
    adv_text = await get_bot_text(
        key="advanced_settings_intro",
        default="تنظیمات نمایش سرویس",
        lang=lang,
    )
    if is_callback:
        buttons = [*buttons, [home_back_button()]]
        try:
            await event.edit(adv_text, buttons=buttons)
        except Exception:
            await event.respond(adv_text, buttons=buttons)
    else:
        await event.respond(adv_text, buttons=buttons)
    await set_step(event.sender_id, "advanced_settings")
    raise events.StopPropagation


async def _qr_text_message_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) != "qr_text":
        return False
    return bool((event.message.text or "").strip())


@bot_is_offline
async def qr_text_message_handler(event: Message):
    msg = event.message.text or ""
    if len(msg) > 512:
        await event.respond("متن شما بیش از حد طولانی است. حداکثر 512 کاراکتر مجاز است")
    else:
        qr_file = create_qr_code(text=msg, filename=f"qr_{event.sender_id}.png")
        await event.respond("🔲 بارکد شما", file=qr_file)
    user = await UserCRUD().read_user(event.sender_id)
    buttons = create_buttons_user_settings(user)
    await event.respond("تنظیمات پیشرفته", buttons=buttons)
    await set_step(event.sender_id, "advanced_settings")
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        advanced_settings_handler,
        events.NewMessage(incoming=True, func=advanced_settings_filter),
    )
    client.add_event_handler(
        qr_text_message_handler,
        events.NewMessage(incoming=True, func=_qr_text_message_filter),
    )

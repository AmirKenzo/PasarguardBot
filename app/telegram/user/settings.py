"""User advanced settings menu and the QR-code text option."""

from __future__ import annotations

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.keyboards import get_button_text
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import bhome_buttons, home_back_button
from app.telegram.keyboards.user_settings import (
    create_buttons_row_count,
    create_buttons_row_size,
    create_buttons_user_settings,
)
from app.telegram.plugins import PluginContext
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import get_step, set_step
from app.utils.media.qrcode import create_qr_code
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

MODULE_NAME = "user.settings"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User advanced display settings"

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
        default=DEFAULT_BOT_TEXTS["advanced_settings_intro"],
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


@bot_is_offline
@debounce_callback()
async def callback_user_settings(event: events.CallbackQuery.Event):
    data = event.data.decode()
    user_id = event.sender_id
    user = await UserCRUD().read_user(user_id)
    lang = user.language if user and user.language else BOT_LANGUAGE
    has_service = await ServiceCRUD().has_active_service(user_id)
    if data != "user_setting.back" and not has_service:
        await event.answer("⛔️ شما هیچ سرویس فعالی ندارید", alert=True)
        return
    if data == "user_setting.back":
        await set_step(event.sender_id, "home")
        await event.edit("تنظیمات پیشرفته بسته شد", buttons=await bhome_buttons(event.sender_id, lang))
        return
    if data == "user_setting.show_volume":
        await UserCRUD().update_user(event.sender_id, show_volume=not user.show_volume)
    elif data == "user_setting.show_panel":
        await UserCRUD().update_user(event.sender_id, show_panel=not user.show_panel)
    elif data == "user_setting.show_service_word":
        await UserCRUD().update_user(event.sender_id, show_service_word=not user.show_service_word)
    elif data == "user_setting.show_config_name":
        await UserCRUD().update_user(event.sender_id, show_config_name=not user.show_config_name)
    elif data == "user_setting.row_size_menu":
        buttons = create_buttons_row_size(user.service_buttons_per_row or 1)
        await event.edit("🕹 تعداد نمایش دکمه‌ها در هر ردیف از (چپ به راست) را انتخاب کنید", buttons=buttons)
        return
    elif data.startswith("user_setting.row_size."):
        if data.endswith("back"):
            buttons = create_buttons_user_settings(user)
            await event.edit("تنظیمات نمایش سرویس", buttons=buttons)
            return
        try:
            value = int(data.rsplit(".", 1)[1])
            if 1 <= value <= 8:
                await UserCRUD().update_user(event.sender_id, service_buttons_per_row=value)
        except ValueError:
            pass
    elif data == "user_setting.row_count_menu":
        buttons = create_buttons_row_count(user.service_button_rows or 1)
        await event.edit("🕹 تعداد نمایش دکمه‌ها در هر ردیف از (بالا به پایین) را انتخاب کنید", buttons=buttons)
        return
    elif data.startswith("user_setting.row_count."):
        if data.endswith("back"):
            buttons = create_buttons_user_settings(user)
            await event.edit("تنظیمات نمایش سرویس", buttons=buttons)
            return
        try:
            value = int(data.rsplit(".", 1)[1])
            if 1 <= value <= 20:
                await UserCRUD().update_user(event.sender_id, service_button_rows=value)
        except ValueError:
            pass
    elif data == "user_setting.qr_text":
        await set_step(event.sender_id, "qr_text")
        await event.edit(
            "متن خود را ارسال کنید تا بارکد ساخته شود",
            buttons=[Button.inline("بازگشت", b"user_setting.qr_text.back")],
        )
        return
    elif data == "user_setting.qr_text.back":
        await set_step(event.sender_id, "advanced_settings")
        buttons = create_buttons_user_settings(user)
        await event.edit("تنظیمات نمایش سرویس", buttons=buttons)
        return
    user = await UserCRUD().read_user(event.sender_id)
    buttons = create_buttons_user_settings(user)
    await event.edit("تنظیمات نمایش سرویس", buttons=buttons)


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(
        advanced_settings_handler,
        events.NewMessage(incoming=True, func=advanced_settings_filter),
    )
    kenzo.add_event_handler(
        qr_text_message_handler,
        events.NewMessage(incoming=True, func=_qr_text_message_filter),
    )
    kenzo.add_event_handler(
        callback_user_settings,
        events.CallbackQuery(pattern=rb"user_setting\..*"),
    )

"""User help menu: /help, the help buttons and the app download callbacks."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from telethon import Button, events
from telethon.errors import MessageNotModifiedError
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.logger import get_logger
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.help import get_help_buttons
from app.telegram.keyboards.home import home_back_button
from app.telegram.plugins import PluginContext
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.messages.message_drafts import send_message_draft
from app.telegram.shared.utils.help_download import app_download_manager, ios_apps, processing_callbacks
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import get_step
from app.telegram.user.start.helpers import get_user_lang
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

MODULE_NAME = "user.help"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User help menu and app download callbacks"

logger = get_logger(__name__)


@bot_is_offline
@debounce_callback()
async def callback_back_to_help(event: events.CallbackQuery.Event):
    lang = await get_user_lang(event.sender_id)
    try:
        help_message_text = await get_bot_text(
            key="help_message",
            default=DEFAULT_BOT_TEXTS["help_message"],
            lang=lang,
        )
        dynamic_buttons = [*await get_help_buttons(event.sender_id), [home_back_button()]]
        await event.edit(help_message_text, buttons=dynamic_buttons)
    except MessageNotModifiedError:
        await event.answer()
    except Exception as e:
        logger.error("Error in callback_back_to_help: %s", e)
        await event.answer("❌ خطا در بازگشت به منوی راهنما", alert=True)
    raise events.StopPropagation


async def _download_once(event: events.CallbackQuery.Event, data: str, download: Callable[[], Awaitable]) -> bool:
    """Run ``download`` unless the same request is already running; False when skipped."""
    key = f"{event.sender_id}:{data}"
    if key in processing_callbacks:
        await event.answer("⏳ در حال پردازش...")
        return False
    processing_callbacks.add(key)
    try:
        await download()
    finally:
        await asyncio.sleep(1)
        processing_callbacks.discard(key)
    return True


@bot_is_offline
async def help_download_user_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    rest = data.removeprefix("Download_")
    manager = app_download_manager
    try:
        if rest.endswith("_all"):
            started = await _download_once(event, data, lambda: manager.download_all_app_files(event, rest[:-4]))
        elif "_t_" in rest:
            app_key, target_id = rest.split("_t_", 1)
            started = await _download_once(
                event, data, lambda: manager.download_app_files_by_target(event, app_key, target_id)
            )
        elif "_os_" in rest:
            app_key, index = rest.rsplit("_os_", 1)
            category = int(index)
            started = await _download_once(
                event, data, lambda: manager.download_app_files_by_category(event, app_key, category)
            )
        elif rest.endswith("_2"):
            started = await _download_once(event, data, lambda: manager.download_app_file(event, rest[:-2]))
        else:
            await manager.send_app_list(event, rest)
            started = True
    except ValueError:
        await event.answer("❌ درخواست نامعتبر", alert=True)
        started = True
    except Exception as e:
        logger.error("help_download user callback: %s", e)
        await event.answer("❌ خطا", alert=True)
        started = True
    if started:
        raise events.StopPropagation


@bot_is_offline
async def help_download_ios_callback(event: events.CallbackQuery.Event):
    try:
        app_key = event.data.decode("utf-8").split("_", 1)[1]
        if app_key not in ios_apps:
            await event.answer("❌ لینک اپ استور یافت نشد!", alert=True)
            return
        buttons = [[Button.inline("بازگشت", "backTOhelp")]]
        try:
            await event.edit(f"دانلود از اپ استور:\n\n{ios_apps[app_key]}", buttons=buttons)
        except MessageNotModifiedError:
            await event.answer()
    except Exception as e:
        logger.error("help_download ios callback: %s", e)
        await event.answer("❌ خطا در نمایش لینک اپ استور", alert=True)

    raise events.StopPropagation


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


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(
        help_menu_handler,
        events.NewMessage(incoming=True, func=help_menu_filter),
    )
    kenzo.add_event_handler(
        callback_back_to_help,
        events.CallbackQuery(data="backTOhelp"),
    )
    kenzo.add_event_handler(
        help_download_user_callback,
        events.CallbackQuery(pattern=rb"^Download_"),
    )
    kenzo.add_event_handler(
        help_download_ios_callback,
        events.CallbackQuery(pattern=rb"^IOS_"),
    )

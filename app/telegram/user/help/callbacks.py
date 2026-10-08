"""Callback handlers for user help (menu + app downloads)."""

from __future__ import annotations

import asyncio

from telethon import Button, events
from telethon.errors import MessageNotModifiedError

from app.logger import get_logger
from app.telegram.keyboards.help import get_help_buttons
from app.telegram.keyboards.home import home_back_button
from app.telegram.shared.utils.help_download import app_download_manager, ios_apps, processing_callbacks
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.user.start.helpers import get_user_lang
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


@bot_is_offline
@debounce_callback()
async def callback_back_to_help(event: events.CallbackQuery.Event):
    lang = await get_user_lang(event.sender_id)
    try:
        help_message_text = await get_bot_text(
            key="help_message",
            default="**تمام اموزش های ربات در این بخش میباشد\n🔰لطفا یکی از گزینه های زیر را انتخاب کنید🔰**",
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


@bot_is_offline
async def help_download_user_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    key = None
    try:
        if data.startswith("Download_") and data.endswith("_all"):
            app_key = data[len("Download_") : -len("_all")]
            key = f"{event.sender_id}:{data}"
            if key in processing_callbacks:
                await event.answer("⏳ در حال پردازش...")
                return
            processing_callbacks.add(key)
            await app_download_manager.download_all_app_files(event, app_key)

        elif data.startswith("Download_") and "_t_" in data:
            rest = data[len("Download_") :]
            parts = rest.split("_t_", 1)
            if len(parts) == 2:
                app_key, target_id = parts[0], parts[1]
                key = f"{event.sender_id}:{data}"
                if key in processing_callbacks:
                    await event.answer("⏳ در حال پردازش...")
                    return
                processing_callbacks.add(key)
                await app_download_manager.download_app_files_by_target(event, app_key, target_id)
            else:
                await event.answer("❌ درخواست نامعتبر", alert=True)

        elif data.startswith("Download_") and "_os_" in data:
            rest = data[len("Download_") :]
            parts = rest.rsplit("_os_", 1)
            if len(parts) == 2:
                app_key = parts[0]
                category_index = int(parts[1])
                key = f"{event.sender_id}:{data}"
                if key in processing_callbacks:
                    await event.answer("⏳ در حال پردازش...")
                    return
                processing_callbacks.add(key)
                await app_download_manager.download_app_files_by_category(event, app_key, category_index)
            else:
                await event.answer("❌ درخواست نامعتبر", alert=True)

        elif data.startswith("Download_") and data.endswith("_2"):
            app_key = data[len("Download_") : -len("_2")]
            key = f"{event.sender_id}:{data}"
            if key in processing_callbacks:
                await event.answer("⏳ در حال پردازش...")
                return
            processing_callbacks.add(key)
            await app_download_manager.download_app_file(event, app_key)

        elif (
            data.startswith("Download_")
            and not data.endswith("_2")
            and not data.endswith("_all")
            and "_os_" not in data
            and "_t_" not in data
        ):
            app_key = data[len("Download_") :]
            await app_download_manager.send_app_list(event, app_key)

        else:
            return

    except ValueError:
        await event.answer("❌ درخواست نامعتبر", alert=True)
    except Exception as e:
        logger.error("help_download user callback: %s", e)
        await event.answer("❌ خطا", alert=True)
    finally:
        if key:
            await asyncio.sleep(1)
            processing_callbacks.discard(key)

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


def register(client):
    client.add_event_handler(
        callback_back_to_help,
        events.CallbackQuery(data="backTOhelp"),
    )
    client.add_event_handler(
        help_download_user_callback,
        events.CallbackQuery(pattern=rb"^Download_"),
    )
    client.add_event_handler(
        help_download_ios_callback,
        events.CallbackQuery(pattern=rb"^IOS_"),
    )

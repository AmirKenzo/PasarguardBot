"""Message handlers for admin settings."""

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.bot_texts import BotTextCRUD
from app.db.crud.help_buttons import HelpButtonCRUD
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.telegram.rich_message import send_native_rich_message
from app.telegram.admin.settings import states, texts
from app.telegram.keyboards.common import extract_custom_emoji_document_id
from app.telegram.keyboards.customization import (
    create_keyboard_button_config_view,
    create_keyboard_buttons_admin_buttons,
)
from app.telegram.keyboards.help import (
    create_help_button_submenu,
    create_help_buttons_config_ui,
    create_help_reorder_ui,
)
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_TITLES
from app.telegram.keyboards.settings import create_buttons_settings, get_settings_menu_text, settings_menu_rich_blocks
from app.telegram.keyboards.texts import TEXT_KEYS_CONFIG, create_text_sections_buttons, render_stored_text_html
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


async def message_handler_settings(event: Message):
    if not event.is_private:
        return
    if await get_step(event.sender_id) != states.PANEL_STEP:
        return

    logger.info("message_handler_settings")
    settings = await SettingsManager().get_settings()
    try:
        blocks = await settings_menu_rich_blocks(settings)
        await send_native_rich_message(event.chat_id, blocks)
    except Exception as rich_exc:
        logger.warning("settings menu rich send failed, falling back: %s", rich_exc)
        buttons = await create_buttons_settings(settings)
        await event.respond(get_settings_menu_text(), buttons=buttons)


async def _settings_admin_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    msg = (event.message.text or "").strip()
    step = await get_step(event.sender_id)
    if step == states.PANEL_STEP and msg in states.SETTINGS_PANEL_MENU_MESSAGES:
        return True
    if step in states.SETTINGS_ADMIN_STEPS:
        return True
    return bool(step and step.startswith(("edit_keyboard:", "edit_text:", "edit_banner_url:")))


async def message_handler_settings_admin(event: Message):
    msg = (event.message.text or "").strip()

    if await get_step(event.sender_id) == "help_btn_reorder_position":
        msg_stripped = (msg or "").strip() if isinstance(msg, str) else ""
        if not msg_stripped:
            await event.respond("یک عدد از ۱ تا N بفرستید (یا /cancel برای انصراف).")
            return
        if msg_stripped.lower() == "/cancel":
            for key in ("help_btn_reorder_id", "help_btn_reorder_msg_id", "help_btn_reorder_chat_id"):
                await delete_data(event.sender_id, key)
            await set_step(event.sender_id, "home")
            await event.respond("انصراف داده شد.")
            return

        normalized = (
            msg_stripped.replace("۰", "0")
            .replace("۱", "1")
            .replace("۲", "2")
            .replace("۳", "3")
            .replace("۴", "4")
            .replace("۵", "5")
            .replace("۶", "6")
            .replace("۷", "7")
            .replace("۸", "8")
            .replace("۹", "9")
            .replace("٠", "0")
            .replace("١", "1")
            .replace("٢", "2")
            .replace("٣", "3")
            .replace("٤", "4")
            .replace("٥", "5")
            .replace("٦", "6")
            .replace("٧", "7")
            .replace("٨", "8")
            .replace("٩", "9")
        )
        num_part = normalized.split()[0] if normalized.split() else normalized
        try:
            k = int(num_part.strip())
        except ValueError, TypeError:
            await event.respond("لطفاً فقط یک عدد بفرستید (مثلاً 5 یا ۱۰). یا /cancel برای انصراف.")
            return
        btn_id_str = await get_data(event.sender_id, "help_btn_reorder_id")
        msg_id_str = await get_data(event.sender_id, "help_btn_reorder_msg_id")
        chat_id_str = await get_data(event.sender_id, "help_btn_reorder_chat_id")
        if not btn_id_str or not msg_id_str or not chat_id_str:
            await event.respond("❌ لطفاً دوباره از منوی ترتیب دکمه‌ها شروع کنید.")
            await set_step(event.sender_id, "home")
            return
        btn_id = int(btn_id_str)
        msg_id = int(msg_id_str)
        chat_id = int(chat_id_str)
        if k < 1:
            await event.respond("عدد باید بزرگ‌تر از ۰ باشد.")
            return
        help_crud = HelpButtonCRUD()
        ok = await help_crud.set_button_number(btn_id, k)
        for key in ("help_btn_reorder_id", "help_btn_reorder_msg_id", "help_btn_reorder_chat_id"):
            await delete_data(event.sender_id, key)
        await set_step(event.sender_id, "home")
        if ok:
            await event.respond("✅ جابه‌جا شد.")
            text, rows = await create_help_reorder_ui(back_data="back_to_help_settings")
            with contextlib.suppress(Exception):
                await Kenzo.edit_message(chat_id, msg_id, text, buttons=rows)
        else:
            await event.respond("❌ خطا در ذخیره ترتیب.")
        return

    if await get_step(event.sender_id) == states.PANEL_STEP and msg == "📝 متن‌های ربات":
        await set_data(event.sender_id, "text_sections_page", "1")
        await Kenzo.send_message(
            entity=event.sender_id,
            message=texts.TEXT_MANAGEMENT_INTRO,
            buttons=create_text_sections_buttons(page=1),
        )
        return

    if await get_step(event.sender_id) == states.PANEL_STEP and msg == "⌨️ مدیریت دکمه‌های کیبورد":
        sent_msg = await Kenzo.send_message(
            entity=event.sender_id,
            message=texts.KEYBOARD_MANAGEMENT_INTRO,
            buttons=await create_keyboard_buttons_admin_buttons(page=1),
        )
        await set_data(event.sender_id, "edit_keyboard_msg_id", str(sent_msg.id))
        return

    if ((await get_step(event.sender_id)) or "").startswith("edit_keyboard:") and msg:
        step_val = await get_step(event.sender_id)
        parts = step_val.split(":") if step_val else []
        button_key = parts[1] if len(parts) >= 2 else None
        page = int(parts[2]) if len(parts) >= 3 else 1

        if not button_key:
            await event.respond("❌ کلید دکمه نامعتبر است.")
        else:
            keyboard_crud = KeyboardButtonCRUD()
            saved = await keyboard_crud.set_button_text(button_key=button_key, button_text=msg)
            prev_msg_id = await get_data(event.sender_id, "edit_keyboard_msg_id")

            if saved:
                success_message = "✅ متن دکمه با موفقیت ذخیره شد."
                pretty = KEYBOARD_BUTTON_TITLES.get(button_key, button_key)
                _, config_buttons = await create_keyboard_button_config_view(button_key, page, keyboard_crud)

                if prev_msg_id:
                    try:
                        await Kenzo.edit_message(
                            entity=event.sender_id,
                            message=int(prev_msg_id),
                            text=f"{success_message}\n\n⌨️ تنظیم دکمه «{pretty}»",
                            buttons=config_buttons,
                        )
                    except Exception as e:
                        logger.error(f"Error editing previous message: {e}")
                        await event.respond(
                            f"{success_message}\n\n⌨️ تنظیم دکمه «{pretty}»",
                            buttons=config_buttons,
                        )
                else:
                    await event.respond(
                        f"{success_message}\n\n⌨️ تنظیم دکمه «{pretty}»",
                        buttons=config_buttons,
                    )
            else:
                error_message = "❌ ذخیره متن دکمه با خطا مواجه شد."
                if prev_msg_id:
                    try:
                        await Kenzo.edit_message(
                            entity=event.sender_id,
                            message=int(prev_msg_id),
                            text=error_message,
                            buttons=[[Button.inline("🔙 بازگشت", data=f"keyboard_page:{page}")]],
                        )
                    except Exception:
                        await event.respond(
                            error_message,
                            buttons=[[Button.inline("🔙 بازگشت", data=f"keyboard_page:{page}")]],
                        )
                else:
                    await event.respond(
                        error_message,
                        buttons=[[Button.inline("🔙 بازگشت", data=f"keyboard_page:{page}")]],
                    )

        await set_data(event.sender_id, "edit_keyboard_msg_id", "")
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if (await get_step(event.sender_id)) == "keyboard_btn_set_icon" and msg:
        button_key = await get_data(event.sender_id, "keyboard_btn_key")
        page = states.parse_stored_page(await get_data(event.sender_id, "keyboard_btn_page"))
        if not button_key:
            await event.respond("❌ خطا: کلید دکمه یافت نشد.")
            await set_step(event.sender_id, "panel")
            return

        keyboard_crud = KeyboardButtonCRUD()
        if msg.strip().lower() == "/skip":
            saved = await keyboard_crud.set_button(button_key, clear_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی معمولی document_id ندارد. از پنل ایموجی‌های پریمیوم تلگرام بفرستید، یا آیدی عددی/فرمت `emoji/ID` را ارسال کنید. برای حذف هم /skip را بفرستید.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_keyboard:{button_key}:{page}")]],
                )
                raise events.StopPropagation
            saved = await keyboard_crud.set_button(button_key, button_icon=icon_id)

        await delete_data(event.sender_id, "keyboard_btn_key")
        await delete_data(event.sender_id, "keyboard_btn_page")
        await set_step(event.sender_id, "panel")
        pretty = KEYBOARD_BUTTON_TITLES.get(button_key, button_key)
        _, config_buttons = await create_keyboard_button_config_view(button_key, page, keyboard_crud)
        await event.respond(
            ("✅ آیکون دکمه تنظیم شد." if saved else "❌ ذخیره آیکون با خطا مواجه شد.")
            + f"\n\n⌨️ تنظیم دکمه «{pretty}»",
            buttons=config_buttons,
        )
        raise events.StopPropagation

    if (await get_step(event.sender_id)) == "help_btn_set_icon" and msg:
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        if not button_num_data:
            await event.respond("❌ خطا: شماره دکمه یافت نشد.")
            await set_step(event.sender_id, "home")
            return

        button_num = int(button_num_data)
        help_crud = HelpButtonCRUD()

        if msg.strip().lower() == "/skip":
            await help_crud.set_button(button_num, clear_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی معمولی document_id ندارد. از پنل ایموجی‌های پریمیوم تلگرام بفرستید، یا آیدی عددی/فرمت `emoji/ID` را ارسال کنید. برای حذف هم /skip را بفرستید.",
                    buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
                )
                raise events.StopPropagation
            await help_crud.set_button(button_num, button_icon=icon_id)

        await delete_data(event.sender_id, "help_btn_num")
        await set_step(event.sender_id, "home")
        submenu = create_help_button_submenu(button_num)
        btn = await help_crud.get_button(button_num)
        await event.respond(
            f"✅ آیکون تنظیم شد.\n\n📝 **دکمه {button_num}**\n{btn.button_text}",
            buttons=submenu,
        )
        raise events.StopPropagation

    if (await get_step(event.sender_id)) == "help_btn_edit_text" and msg:
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        if not button_num_data:
            await event.respond("❌ خطا: شماره دکمه یافت نشد.")
            await set_step(event.sender_id, "home")
            return

        button_num = int(button_num_data)
        help_crud = HelpButtonCRUD()
        btn = await help_crud.get_button(button_num)
        if not btn or not btn.button_url:
            await event.respond("❌ دکمه یافت نشد.")
            await delete_data(event.sender_id, "help_btn_num")
            await set_step(event.sender_id, "home")
            return

        await help_crud.set_button(button_num, button_text=msg)
        await delete_data(event.sender_id, "help_btn_num")
        await set_step(event.sender_id, "home")
        buttons = await create_help_buttons_config_ui()
        await event.respond("✅ متن دکمه به‌روزرسانی شد.", buttons=buttons)
        raise events.StopPropagation

    if (await get_step(event.sender_id)) == "help_btn_edit_link" and msg:
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        if not button_num_data:
            await event.respond("❌ خطا: شماره دکمه یافت نشد.")
            await set_step(event.sender_id, "home")
            return

        button_num = int(button_num_data)
        button_url = msg.strip()
        if not button_url.startswith(("http://", "https://", "tg://", "t.me/")):
            await event.respond(
                "❌ آدرس نامعتبر. مثال: https://t.me/ یا tg://",
                buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
            )
            raise events.StopPropagation

        if button_url.startswith("t.me/"):
            button_url = "https://" + button_url

        help_crud = HelpButtonCRUD()
        await help_crud.set_button(button_num, button_url=button_url)
        await delete_data(event.sender_id, "help_btn_num")
        await set_step(event.sender_id, "home")
        buttons = await create_help_buttons_config_ui()
        await event.respond("✅ لینک دکمه به‌روزرسانی شد.", buttons=buttons)
        raise events.StopPropagation

    # Admin: Help button configuration (text and URL)
    if (await get_step(event.sender_id)) == "help_btn_set_text" and msg:
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        if not button_num_data:
            await event.respond("❌ خطا: شماره دکمه یافت نشد.")
            await delete_data(event.sender_id, "help_btn_num")
            await set_step(event.sender_id, "home")
            return

        button_num = int(button_num_data)
        help_crud = HelpButtonCRUD()

        # Store text and ask for URL
        await set_data(event.sender_id, "help_btn_text", msg)
        await set_step(event.sender_id, "help_btn_set_url")

        await event.respond(
            f"✅ متن دکمه {button_num} ذخیره شد: {msg}\n\nلطفا آدرس (URL) دکمه را ارسال کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
        )
        return

    if (await get_step(event.sender_id)) == "help_btn_set_url" and msg:
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        button_text_data = await get_data(event.sender_id, "help_btn_text")

        if not button_num_data or not button_text_data:
            await event.respond("❌ خطا: اطلاعات دکمه یافت نشد.")
            await delete_data(event.sender_id, "help_btn_num")
            await delete_data(event.sender_id, "help_btn_text")
            await set_step(event.sender_id, "home")
            return

        button_num = int(button_num_data)
        button_text = button_text_data
        button_url = msg.strip()

        # Validate URL
        if not button_url.startswith(("http://", "https://", "tg://", "t.me/")):
            await event.respond(
                "❌ آدرس نامعتبر است. لطفا یک آدرس معتبر ارسال کنید (مثال: https://t.me/ یا tg://)",
                buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
            )
            return

        # Normalize t.me/ to https://t.me/
        if button_url.startswith("t.me/"):
            button_url = "https://" + button_url

        help_crud = HelpButtonCRUD()
        success = await help_crud.set_button(button_num, button_text, button_url)

        if success:
            await set_data(event.sender_id, "help_btn_url", button_url)
            await set_step(event.sender_id, "help_btn_set_style")

            await event.respond(
                f"✅ متن و آدرس دکمه {button_num} ذخیره شد.\n\nرنگ دکمه را انتخاب کنید (یا رد کردن برای بدون رنگ):",
                buttons=[
                    [
                        Button.inline("آبی", data="help_btn_style:primary"),
                        Button.inline("سبز", data="help_btn_style:success"),
                        Button.inline("قرمز", data="help_btn_style:danger"),
                    ],
                    [Button.inline("رد کردن (بدون رنگ)", data="help_btn_style:skip")],
                    [Button.inline("🔙 بازگشت", data="back_to_help_config")],
                ],
            )
        else:
            await event.respond(
                "❌ خطا در ذخیره دکمه. لطفا دوباره تلاش کنید.",
                buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
            )
        return

    # Admin: Preview bot text before saving (with confirmation)
    if ((await get_step(event.sender_id)) or "").startswith("edit_text:") and msg:
        step_val = await get_step(event.sender_id)

        # Only process if step is exactly edit_text:key:lang or edit_text:key:lang:sections_page
        if not step_val or not step_val.startswith("edit_text:"):
            return

        parts = step_val.split(":") if step_val else []
        # Must have at least key and lang (parts[1] and parts[2])
        if len(parts) < 3:
            return

        key = parts[1] if len(parts) >= 2 else None
        lang_code = parts[2] if len(parts) >= 3 else None

        # Get sections_page from step or callback
        sections_page = 1
        if len(parts) >= 4 and parts[3].isdigit():
            sections_page = int(parts[3])
        else:
            sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

        if not key or not lang_code:
            await event.respond("❌ کلید متن یا زبان نامعتبر است.")
            return

        # Find key config for title
        key_config = None
        section_key = None
        for sec, keys_list in TEXT_KEYS_CONFIG.items():
            for kc in keys_list:
                if kc["key"] == key:
                    key_config = kc
                    section_key = sec
                    break
            if key_config:
                break

        pretty = key_config["title"] if key_config else key

        # Show preview with confirmation buttons
        preview_text = (
            f"📝 **پیش‌نمایش متن جدید برای «{pretty}»**\n\n"
            f"<blockquote expandable>{render_stored_text_html(msg)}</blockquote>\n\n"
            f"⚠️ آیا می‌خواهید این متن را ذخیره کنید؟"
        )

        buttons = [
            [Button.inline("✅ بله، ذخیره کن", data=f"confirm_save_text:{key}:{lang_code}:{sections_page}")],
            [Button.inline("❌ خیر، لغو", data=f"cancel_save_text:{key}:{lang_code}:{sections_page}")],
        ]

        # Store the message text temporarily
        await set_data(event.sender_id, "pending_text_value", msg)
        prev_msg_id = await get_data(event.sender_id, "edit_text_msg_id")

        # Delete previous bot message only (not user's message)
        if prev_msg_id:
            try:
                await Kenzo.delete_messages(entity=event.sender_id, message_ids=[int(prev_msg_id)])
            except Exception as e:
                logger.error(f"Error deleting previous message: {e}")

        # Send preview message
        sent_msg = await event.respond(
            preview_text,
            buttons=buttons,
            parse_mode="html",
        )
        await set_data(event.sender_id, "edit_text_msg_id", str(sent_msg.id))
        return
    # Admin: Save banner URL
    if ((await get_step(event.sender_id)) or "").startswith("edit_banner_url:") and msg is not None:
        step_val = await get_step(event.sender_id)
        parts = step_val.split(":") if step_val else []
        key = parts[1] if len(parts) >= 2 else None
        lang_code = parts[2] if len(parts) >= 3 else None
        sections_page = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1

        if not key:
            await event.respond("❌ کلید متن نامعتبر است.")
        else:
            # Get existing bot text to preserve value and position
            bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
            current_value = bot_text_obj.value if bot_text_obj else ""
            current_position = bot_text_obj.banner_position if bot_text_obj else None

            # If message is empty or just whitespace, remove banner
            banner_url = msg.strip() if msg.strip() else None

            saved = await BotTextCRUD().set_text(
                key=key,
                value=current_value,
                lang=lang_code,
                banner_url=banner_url,
                banner_position=current_position,
            )

            # Find section for back button
            section_key = None
            for sec, keys_list in TEXT_KEYS_CONFIG.items():
                for kc in keys_list:
                    if kc["key"] == key:
                        section_key = sec
                        break
                if section_key:
                    break

            sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

            if saved:
                if banner_url:
                    await event.respond(
                        "✅ لینک بنر با موفقیت ذخیره شد.",
                        buttons=[[Button.inline("🔙 بازگشت", data=f"edit_text:{key}:{lang_code}:{sections_page}")]],
                    )
                else:
                    await event.respond(
                        "✅ بنر حذف شد.",
                        buttons=[[Button.inline("🔙 بازگشت", data=f"edit_text:{key}:{lang_code}:{sections_page}")]],
                    )
                await set_step(event.sender_id, f"edit_text:{key}:{lang_code}:{sections_page}")
            else:
                await event.respond("❌ ذخیره لینک بنر با خطا مواجه شد.")


def register(client):
    client.add_event_handler(
        message_handler_settings,
        events.NewMessage(pattern=states.SETTINGS_MENU_MESSAGE_PATTERN, incoming=True, from_users=ADMIN_ID),
    )
    client.add_event_handler(
        message_handler_settings_admin,
        events.NewMessage(incoming=True, func=_settings_admin_message_filter, from_users=ADMIN_ID),
    )

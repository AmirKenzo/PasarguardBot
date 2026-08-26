"""Callback handlers for admin settings."""

import contextlib

from telethon import Button, events
from telethon.errors.rpcerrorlist import MessageNotModifiedError

from app.db.crud.bot_texts import BotTextCRUD
from app.db.crud.help_buttons import HelpButtonCRUD
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.telegram.rich_message import edit_native_rich_message
from app.telegram.admin.settings import keyboards, states, texts
from app.telegram.keyboards.customization import (
    create_keyboard_button_config_view,
    create_keyboard_buttons_admin_buttons,
)
from app.telegram.keyboards.help import (
    create_help_button_submenu,
    create_help_buttons_config_ui,
    create_help_reorder_ui,
)
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_TITLES, STYLE_LABELS
from app.telegram.keyboards.settings import (
    create_buttons_settings,
    get_settings_menu_item,
    get_settings_menu_section,
    get_settings_menu_text,
    get_settings_section_key_for_attr,
    settings_menu_rich_blocks,
)
from app.telegram.keyboards.texts import (
    TEXT_KEYS_CONFIG,
    TEXT_SECTIONS,
    build_edit_text_view,
    create_language_select_buttons,
    create_text_keys_buttons,
    create_text_sections_buttons,
    render_stored_text_html,
)
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from app.telegram.user.start.helpers import toggle_start_reaction
from config import ADMIN_ID

logger = get_logger(__name__)


async def _edit_settings_menu(event: events.CallbackQuery.Event, settings, section_key: str | None = None) -> None:
    try:
        blocks = await settings_menu_rich_blocks(settings, section_key=section_key)
        await edit_native_rich_message(event, blocks)
    except Exception as rich_exc:
        logger.warning("settings menu rich edit failed, falling back: %s", rich_exc)
        buttons = await create_buttons_settings(settings, section_key=section_key)
        await event.edit(get_settings_menu_text(section_key), buttons=buttons)


def settings_callback_filter(event: events.CallbackQuery.Event) -> bool:
    """Filter for settings callbacks - only admin users with data starting with 'settings.'"""
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    return data.startswith("settings.")


async def callback_settings_menu_page(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != states.PANEL_STEP:
        return

    data = event.data.decode("utf-8")
    section_key = None if data in {"settings_menu", "settings_menu:home"} else data.removeprefix("settings_menu:")
    if section_key and get_settings_menu_section(section_key) is None:
        await event.answer("این بخش تنظیمات پیدا نشد.", alert=True)
        return

    await event.answer()
    settings = await SettingsManager().get_settings()
    await _edit_settings_menu(event, settings, section_key)


async def callback_settings_toggle(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != states.PANEL_STEP:
        return

    data = event.data.decode("utf-8")
    setting_name = data.removeprefix("settings.")
    settings = await SettingsManager().get_settings()
    if not settings:
        await event.answer("تنظیمات ربات پیدا نشد.", alert=True)
        return

    try:
        item = get_settings_menu_item(setting_name)
        if item is None:
            await event.answer("این گزینه تنظیمات پیدا نشد.", alert=True)
            return

        if setting_name == "start_reaction":
            new_value = await toggle_start_reaction()
            toast = f"{item.label}: {'✅ فعال شد' if new_value else '❌ غیرفعال شد'}"
        else:
            current_value = bool(getattr(settings, setting_name, item.default))
            update_kwargs = {setting_name: not current_value}
            if setting_name == "pay_mode" and not current_value:
                update_kwargs["manual_card_visibility"] = None
            await SettingsManager().update_setting(settings.id, **update_kwargs)
            toast = f"{item.label}: {'❌ غیرفعال شد' if current_value else '✅ فعال شد'}"
    except Exception as e:
        await event.answer(f"خطا در به‌روزرسانی تنظیمات: {e!s}", alert=True)
        return

    await event.answer(toast)
    updated_settings = await SettingsManager().get_settings()
    await _edit_settings_menu(
        event,
        updated_settings,
        get_settings_section_key_for_attr(setting_name),
    )


def settings_admin_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    if data in states.SETTINGS_CALLBACK_EXACT:
        return True
    return any(data.startswith(p) for p in states.SETTINGS_CALLBACK_PREFIXES)


async def callback_settings_admin(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")

    if data == "help_settings_admin":
        await event.edit(texts.HELP_SETTINGS_MENU_TEXT, buttons=keyboards.help_settings_menu_buttons())

    if data == "back_to_help_settings":
        await event.edit(texts.HELP_SETTINGS_MENU_TEXT, buttons=keyboards.help_settings_menu_buttons())

    if data == "help_settings_reorder_buttons":
        text, rows = await create_help_reorder_ui(back_data="back_to_help_settings")
        try:
            await event.edit(text, buttons=rows)
        except MessageNotModifiedError:
            await event.answer()
        return

    if data.startswith("help_btn_reorder_set:"):
        try:
            btn_id = int(data.split(":")[1])
            help_crud = HelpButtonCRUD()
            btn = await help_crud.get_by_id(btn_id)
            if not btn:
                await event.answer("❌ دکمه یافت نشد", alert=True)
                return
            label = (btn.button_text or "").strip() or ("اپ" if getattr(btn, "callback_key", None) else "لینک")
            await set_data(event.sender_id, "help_btn_reorder_id", str(btn_id))
            await set_data(event.sender_id, "help_btn_reorder_msg_id", str(event.message_id))
            await set_data(event.sender_id, "help_btn_reorder_chat_id", str(event.chat_id))
            await set_step(event.sender_id, "help_btn_reorder_position")
            prompt = (
                f"📐 **شماره دکمه:** «{label}»\n\n"
                f"**هر عدد دلخواه** را بفرستید (همون عدد به عنوان button_number ذخیره می‌شه)، مثلاً ۱، ۱۷، ۱۰۰۰."
            )
            await event.edit(prompt, buttons=[[Button.inline("❌ انصراف", data="help_btn_reorder_cancel")]])
            await event.answer()
        except ValueError, IndexError:
            await event.answer("❌ درخواست نامعتبر", alert=True)
        return

    if data == "help_btn_reorder_cancel":
        for key in ("help_btn_reorder_id", "help_btn_reorder_msg_id", "help_btn_reorder_chat_id"):
            await delete_data(event.sender_id, key)
        await set_step(event.sender_id, "home")
        text, rows = await create_help_reorder_ui(back_data="back_to_help_settings")
        try:
            await event.edit(text, buttons=rows)
        except MessageNotModifiedError:
            await event.answer()
        return

    if data == "help_settings_buttons_ui":
        buttons = await create_help_buttons_config_ui(back_data="back_to_help_settings")
        await event.edit(
            "✏️ **دکمه‌های لینک (۱ تا ۸)**\n\n"
            "روی هر مورد کلیک → تنظیم متن، لینک، رنگ و آیکون. خالی = در راهنما نشان داده نمی‌شود.",
            buttons=buttons,
        )
        return
    if data.startswith("edit_keyboard:"):
        parts = data.split(":")
        # format: edit_keyboard:button_key:page
        button_key = parts[1] if len(parts) >= 2 else None
        page = int(parts[2]) if len(parts) >= 3 else 1

        if not button_key:
            await event.answer("❌ کلید دکمه نامعتبر است.", alert=True)
            return

        keyboard_crud = KeyboardButtonCRUD()
        preview, buttons = await create_keyboard_button_config_view(button_key, page, keyboard_crud)

        await set_data(event.sender_id, "edit_keyboard_msg_id", str(event.original_update.msg_id))
        await event.edit(
            preview,
            buttons=buttons,
        )
        return

    if data.startswith("keyboard_btn_edit_text:"):
        parts = data.split(":")
        button_key = parts[1] if len(parts) >= 2 else None
        page = int(parts[2]) if len(parts) >= 3 else 1
        if not button_key:
            await event.answer("❌ کلید دکمه نامعتبر است.", alert=True)
            return
        button_obj = await KeyboardButtonCRUD().get_button(button_key)
        current_text = button_obj.button_text if button_obj else None
        pretty = KEYBOARD_BUTTON_TITLES.get(button_key, button_key)
        preview = (
            f"📝 متن فعلی دکمه «{pretty}»:\n<blockquote expandable>{current_text or 'ثبت نشده'}</blockquote>\n\n"
            "لطفاً متن جدید را ارسال کنید:"
        )
        await set_step(event.sender_id, f"edit_keyboard:{button_key}:{page}")
        await set_data(event.sender_id, "edit_keyboard_msg_id", str(event.original_update.msg_id))
        await event.edit(
            preview,
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_keyboard:{button_key}:{page}")]],
            parse_mode="html",
        )
        return

    if data.startswith("keyboard_btn_color:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        button_key = parts[1]
        page = int(parts[2])
        style_val = parts[3]
        keyboard_crud = KeyboardButtonCRUD()
        if style_val == "none":
            saved = await keyboard_crud.set_button(button_key, button_style="")
            success_msg = "رنگ دکمه حذف شد."
        else:
            saved = await keyboard_crud.set_button(button_key, button_style=style_val)
            success_msg = f"رنگ تغییر کرد به {STYLE_LABELS.get(style_val, style_val)}."
        await event.answer(success_msg if saved else "❌ ذخیره رنگ با خطا مواجه شد.", alert=not saved)
        preview, buttons = await create_keyboard_button_config_view(button_key, page, keyboard_crud)
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                preview,
                buttons=buttons,
            )
        return

    if data.startswith("keyboard_btn_icon:"):
        parts = data.split(":")
        button_key = parts[1] if len(parts) >= 2 else None
        page = int(parts[2]) if len(parts) >= 3 else 1
        if not button_key:
            await event.answer("❌ کلید دکمه نامعتبر است.", alert=True)
            return
        await set_data(event.sender_id, "keyboard_btn_key", button_key)
        await set_data(event.sender_id, "keyboard_btn_page", str(page))
        await set_step(event.sender_id, "keyboard_btn_set_icon")
        await event.edit(
            "📎 آیدی سند ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_keyboard:{button_key}:{page}")]],
        )
        return

    if data.startswith("keyboard_btn_icon_clear:"):
        parts = data.split(":")
        button_key = parts[1] if len(parts) >= 2 else None
        page = int(parts[2]) if len(parts) >= 3 else 1
        if not button_key:
            await event.answer("❌ کلید دکمه نامعتبر است.", alert=True)
            return
        keyboard_crud = KeyboardButtonCRUD()
        saved = await keyboard_crud.set_button(button_key, clear_icon=True)
        await event.answer("آیکون دکمه حذف شد." if saved else "❌ حذف آیکون با خطا مواجه شد.", alert=not saved)
        preview, buttons = await create_keyboard_button_config_view(button_key, page, keyboard_crud)
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                preview,
                buttons=buttons,
            )
        return

    if data.startswith("keyboard_page:"):
        try:
            page = int(data.split(":")[1])

            page_titles = {
                1: "📄 **صفحه 1 از 4:** دکمه‌های منوی اصلی",
                2: "📄 **صفحه 2 از 4:** دکمه‌های بخش سرویس‌های من",
                3: "📄 **صفحه 3 از 4:** دکمه‌های افزایش موجودی",
                4: "📄 **صفحه 4 از 4:** دکمه‌های خرید سرویس",
            }
            message_text = f"⌨️ یکی از دکمه‌های کیبورد را برای ویرایش انتخاب کنید:\n\n{page_titles.get(page, '')}"

            await event.edit(
                message_text,
                buttons=await create_keyboard_buttons_admin_buttons(page=page),
            )

            await set_data(event.sender_id, "edit_keyboard_msg_id", str(event.original_update.msg_id))
        except (ValueError, IndexError) as e:
            logger.error(f"Error in keyboard_page handler: {e}")
            await event.answer("❌ خطا در تغییر صفحه", alert=True)
        return

    if data.startswith("text_sections_page:"):
        try:
            page = int(data.split(":")[1])

            total_sections = len(TEXT_SECTIONS)
            per_page = 8
            num_pages = (total_sections + per_page - 1) // per_page
            page = max(1, min(page, num_pages))

            # Clear edit_text step to prevent text saving when user is browsing
            current_step = await get_step(event.sender_id)
            if current_step and current_step.startswith("edit_text:"):
                await set_step(event.sender_id, "panel")
                await set_data(event.sender_id, "pending_text_value", "")
                await set_data(event.sender_id, "edit_text_msg_id", "")

            # Save sections_page in step manager
            await set_data(event.sender_id, "text_sections_page", str(page))

            message_text = (
                f"📝 **مدیریت متن‌های ربات**\n\n**صفحه {page} از {num_pages}**\n\nیکی از بخش‌های زیر را انتخاب کنید:"
            )
            await event.edit(
                message_text,
                buttons=create_text_sections_buttons(page=page),
            )
            await set_data(event.sender_id, "text_management_msg_id", str(event.original_update.msg_id))
        except (ValueError, IndexError) as e:
            logger.error(f"Error in text_sections_page handler: {e}")
            await event.answer("❌ خطا در بارگذاری بخش‌ها", alert=True)
        return

    if data.startswith("text_section:"):
        try:
            parts = data.split(":")
            section = parts[1]
            page = int(parts[2]) if len(parts) > 2 else 1
            # Get sections_page from step manager
            sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

            if section not in TEXT_SECTIONS:
                await event.answer("❌ بخش نامعتبر", alert=True)
                return

            # Clear edit_text step to prevent text saving when user is browsing
            current_step = await get_step(event.sender_id)
            if current_step and current_step.startswith("edit_text:"):
                await set_step(event.sender_id, "panel")
                await set_data(event.sender_id, "pending_text_value", "")
                await set_data(event.sender_id, "edit_text_msg_id", "")

            section_info = TEXT_SECTIONS[section]
            keys_list = TEXT_KEYS_CONFIG.get(section, [])
            total_keys = len(keys_list)
            per_page = 10
            num_pages = (total_keys + per_page - 1) // per_page
            page = max(1, min(page, num_pages))

            message_text = (
                f"📝 **{section_info['icon']} {section_info['name']}**\n\n"
                f"**صفحه {page} از {num_pages}** ({total_keys} متن)\n\n"
                f"یکی از متن‌های زیر را برای ویرایش انتخاب کنید:"
            )
            await event.edit(
                message_text,
                buttons=create_text_keys_buttons(section=section, page=page, sections_page=sections_page),
            )
            await set_data(event.sender_id, "text_management_msg_id", str(event.original_update.msg_id))
        except (ValueError, IndexError) as e:
            logger.error(f"Error in text_section handler: {e}")
            await event.answer("❌ خطا در بارگذاری بخش", alert=True)
        return

    if data.startswith("text_keys_page:"):
        try:
            parts = data.split(":")
            section = parts[1]
            page = int(parts[2])
            sections_page = int(parts[3]) if len(parts) > 3 else 1

            if section not in TEXT_SECTIONS:
                await event.answer("❌ بخش نامعتبر", alert=True)
                return

            # Clear edit_text step to prevent text saving when user is browsing
            current_step = await get_step(event.sender_id)
            if current_step and current_step.startswith("edit_text:"):
                await set_step(event.sender_id, "panel")
                await set_data(event.sender_id, "pending_text_value", "")
                await set_data(event.sender_id, "edit_text_msg_id", "")

            section_info = TEXT_SECTIONS[section]
            keys_list = TEXT_KEYS_CONFIG.get(section, [])
            total_keys = len(keys_list)
            per_page = 10
            num_pages = (total_keys + per_page - 1) // per_page
            page = max(1, min(page, num_pages))

            message_text = (
                f"📝 **{section_info['icon']} {section_info['name']}**\n\n"
                f"**صفحه {page} از {num_pages}** ({total_keys} متن)\n\n"
                f"یکی از متن‌های زیر را برای ویرایش انتخاب کنید:"
            )
            await event.edit(
                message_text,
                buttons=create_text_keys_buttons(section=section, page=page, sections_page=sections_page),
            )
        except (ValueError, IndexError) as e:
            logger.error(f"Error in text_keys_page handler: {e}")
            await event.answer("❌ خطا در بارگذاری صفحه", alert=True)
        return

    if data.startswith("edit_text:"):
        parts = data.split(":")
        # edit_text:<key> or edit_text:<key>:<sections_page>
        if len(parts) == 2 or (len(parts) == 3 and parts[2].isdigit()):
            key = parts[1]
            sections_page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

            # Find key in config
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

            if not key_config:
                await event.answer("❌ کلید متن یافت نشد", alert=True)
                return

            pretty = key_config["title"]
            placeholders = key_config.get("placeholders", {})

            placeholder_info = ""
            if placeholders:
                placeholder_list = "\n".join([f"• `{{{ph}}}`: {desc}" for ph, desc in placeholders.items()])
                placeholder_info = f"\n\n**🔧 پلیس‌هولدر های موجود:**\n{placeholder_list}\n\n💡 می‌توانید از این پلیس‌هولدر ها در متن خود استفاده کنید."
            else:
                placeholder_info = "\n\nℹ️ **این متن پلیس‌هولدر  ندارد.**"

            await set_data(event.sender_id, "text_sections_page", str(sections_page))
            sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

            await event.edit(
                f"🌐 لطفاً زبان متن «{pretty}» را انتخاب کنید:{placeholder_info}",
                buttons=create_language_select_buttons(key, sections_page=sections_page, section_key=section_key),
            )
            return
        # edit_text:<key>:<lang> or edit_text:<key>:<lang>:<sections_page>
        if len(parts) >= 3:
            key = parts[1]
            lang_code = parts[2]
            sections_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

            # Get sections_page from step if not in callback
            if len(parts) == 3:
                sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

            await set_step(event.sender_id, f"edit_text:{key}:{lang_code}:{sections_page}")
            await set_data(event.sender_id, "edit_text_msg_id", str(event.original_update.msg_id))
            await set_data(event.sender_id, "text_sections_page", str(sections_page))

            preview, buttons = await build_edit_text_view(key, lang_code, sections_page)
            await event.edit(
                preview,
                buttons=buttons,
                parse_mode="html",
            )
            return
    if data.startswith("reset_text:"):
        parts = data.split(":")
        if len(parts) >= 3:
            key = parts[1]
            lang_code = parts[2]
            sections_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

            # Get sections_page from step if not in callback
            if len(parts) == 3:
                sections_page = states.parse_stored_page(await get_data(event.sender_id, "text_sections_page"))

            deleted = await BotTextCRUD().delete_text(key=key, lang=lang_code)
            if deleted:
                await event.answer("✅ متن به حالت پیش‌فرض برگشت (از دیتابیس حذف شد)", alert=False)

                # Find section for back button
                section_key = None
                for sec, keys_list in TEXT_KEYS_CONFIG.items():
                    for kc in keys_list:
                        if kc["key"] == key:
                            section_key = sec
                            break
                    if section_key:
                        break

                back_button_data = (
                    f"text_section:{section_key}:1:{sections_page}"
                    if section_key
                    else f"text_sections_page:{sections_page}"
                )

                # Return to edit_text view
                await event.edit(
                    "✅ متن به حالت پیش‌فرض برگشت.\n\nاکنون می‌توانید متن جدیدی تنظیم کنید یا از پیش‌فرض استفاده شود.",
                    buttons=[[Button.inline("🔙 بازگشت", data=back_button_data)]],
                )
            else:
                await event.answer("⚠️ متن یافت نشد یا قبلاً از پیش‌فرض استفاده می‌کند", alert=True)
        return

    if data.startswith("confirm_save_text:"):
        parts = data.split(":")
        if len(parts) >= 4:
            key = parts[1]
            lang_code = parts[2]
            sections_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

            # Get pending text value
            pending_text = await get_data(event.sender_id, "pending_text_value")
            if not pending_text:
                await event.answer("❌ متن یافت نشد. لطفاً دوباره تلاش کنید.", alert=True)
                return

            # Get existing banner settings to preserve them
            bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
            banner_url = bot_text_obj.banner_url if bot_text_obj else None
            banner_position = bot_text_obj.banner_position if bot_text_obj else None

            saved = await BotTextCRUD().set_text(
                key=key,
                value=pending_text,
                lang=lang_code,
                banner_url=banner_url,
                banner_position=banner_position,
            )

            if saved:
                await event.answer("✅ متن با موفقیت ذخیره شد.", alert=False)

                # Return to edit_text view - reload the edit_text page
                bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
                current_val = bot_text_obj.value if bot_text_obj else None
                banner_url = bot_text_obj.banner_url if bot_text_obj else None
                banner_position = bot_text_obj.banner_position if bot_text_obj else None

                # Find key in config
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
                placeholders = key_config.get("placeholders", {}) if key_config else {}

                placeholder_info = ""
                if placeholders:
                    placeholder_list = "\n".join(
                        [f"• <code>{{{ph}}}</code>: {desc}" for ph, desc in placeholders.items()]
                    )
                    placeholder_info = f"\n\n<b>🔧 پلیس‌هولدر های موجود:</b>\n{placeholder_list}\n\n💡 می‌توانید از این پلیس‌هولدر ها در متن خود استفاده کنید."
                else:
                    placeholder_info = "\n\nℹ️ این متن پلیس‌هولدر ندارد."

                banner_info = ""
                if banner_url:
                    position_text = (
                        "بالا" if banner_position == "top" else "پایین" if banner_position == "bottom" else "ست نشده"
                    )
                    banner_info = f"\n\n<b>🖼️ بنر:</b>\n• لینک: `{banner_url}`\n• موقعیت: {position_text}"
                else:
                    banner_info = "\n\n<b>🖼️ بنر:</b> ست نشده"

                if current_val:
                    preview = (
                        f"📝 متن فعلی ({'فارسی' if lang_code == 'fa' else 'انگلیسی'}):\n"
                        f"<blockquote expandable>{render_stored_text_html(current_val)}</blockquote>"
                        f"{banner_info}"
                        f"{placeholder_info}\n\n"
                        f"<b>لطفاً متن جدید برای «{pretty}» را ارسال کنید یا یکی از گزینه‌های زیر را انتخاب کنید.</b>"
                    )
                else:
                    preview = (
                        f"⚠️ برای این زبان هنوز متنی ست نشده است."
                        f"{banner_info}"
                        f"{placeholder_info}\n\n"
                        f"<b>لطفاً متن جدید برای «{pretty}» را ارسال کنید یا یکی از گزینه‌های زیر را انتخاب کنید.</b>"
                    )

                buttons = [
                    [Button.inline("🖼️ تغییر لینک بنر", data=f"edit_banner_url:{key}:{lang_code}:{sections_page}")],
                    [Button.inline("🔄 ریست به پیش‌فرض", data=f"reset_text:{key}:{lang_code}:{sections_page}")],
                ]
                if section_key:
                    buttons.append([Button.inline("🔙 بازگشت", data=f"text_section:{section_key}:1:{sections_page}")])
                else:
                    buttons.append([Button.inline("🔙 بازگشت", data=f"text_sections_page:{sections_page}")])

                await event.edit(
                    preview,
                    buttons=buttons,
                    parse_mode="html",
                )

                # Update step to edit_text
                await set_step(event.sender_id, f"edit_text:{key}:{lang_code}:{sections_page}")
                await set_data(event.sender_id, "edit_text_msg_id", str(event.original_update.msg_id))
            else:
                await event.answer("❌ خطا در ذخیره متن.", alert=True)

            # Clean up
            await set_data(event.sender_id, "pending_text_value", "")
        return

    if data.startswith("cancel_save_text:"):
        parts = data.split(":")
        if len(parts) >= 4:
            key = parts[1]
            lang_code = parts[2]
            sections_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

            await event.answer("❌ ذخیره متن لغو شد.", alert=False)

            # Return to edit_text view - reload the edit_text page
            preview, buttons = await build_edit_text_view(key, lang_code, sections_page)
            await event.edit(
                preview,
                buttons=buttons,
                parse_mode="html",
            )

            # Update step to edit_text
            await set_step(event.sender_id, f"edit_text:{key}:{lang_code}:{sections_page}")
            await set_data(event.sender_id, "edit_text_msg_id", str(event.original_update.msg_id))

            # Clean up
            await set_data(event.sender_id, "pending_text_value", "")
        return

    if data.startswith("edit_banner_url:"):
        parts = data.split(":")
        if len(parts) >= 3:
            key = parts[1]
            lang_code = parts[2]
            sections_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

            bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
            current_banner = bot_text_obj.banner_url if bot_text_obj else None

            preview = "🖼️ **تغییر لینک بنر**\n\n"
            if current_banner:
                preview += f"لینک فعلی: `{current_banner}`\n\n"
            preview += "لطفاً لینک بنر جدید را ارسال کنید (یا یک خط خالی برای حذف بنر):"

            await set_step(event.sender_id, f"edit_banner_url:{key}:{lang_code}:{sections_page}")
            await event.edit(
                preview,
                buttons=[[Button.inline("🔙 بازگشت", data=f"edit_text:{key}:{lang_code}:{sections_page}")]],
                parse_mode="html",
            )
            return

    if data.startswith("set_banner_position:"):
        parts = data.split(":")
        if len(parts) >= 4:
            key = parts[1]
            lang_code = parts[2]
            position = parts[3]
            sections_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 1

            bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
            if bot_text_obj:
                success = await BotTextCRUD().set_banner(
                    key=key, banner_url=bot_text_obj.banner_url, banner_position=position, lang=lang_code
                )
                if success:
                    await event.answer("✅ موقعیت بنر با موفقیت تغییر کرد.", alert=False)
                    # Return to edit_text view
                    preview, buttons = await build_edit_text_view(key, lang_code, sections_page)
                    await event.edit(
                        preview,
                        buttons=buttons,
                        parse_mode="html",
                    )
                else:
                    await event.answer("❌ خطا در ذخیره موقعیت بنر.", alert=True)
            else:
                await event.answer("❌ ابتدا باید متن را ایجاد کنید.", alert=True)
            return
    # Help button configuration handlers (must be before settings block)
    elif data == "help_btn_add":
        help_crud = HelpButtonCRUD()
        all_btns = await help_crud.get_all_buttons()
        max_num = max((b.button_number for b in all_btns), default=0)
        new_num = max_num + 1
        await set_data(event.sender_id, "help_btn_num", str(new_num))
        await set_step(event.sender_id, "help_btn_set_text")
        await event.edit(
            f"📝 **دکمه جدید ({new_num})**\n\nمتن دکمه را ارسال کنید:",
            buttons=[[Button.inline("🔙 انصراف", data="back_to_help_config")]],
        )
        await event.answer()
        return

    if data.startswith("help_btn_config:"):
        button_num = int(data.split(":")[1])
        help_crud = HelpButtonCRUD()
        btn = await help_crud.get_button(button_num)

        if btn and btn.button_text and btn.button_url:
            submenu = create_help_button_submenu(button_num)
            await event.edit(
                f"📝 **دکمه {button_num}**\n{btn.button_text}\n\nانتخاب کنید:",
                buttons=submenu,
            )
        else:
            await set_data(event.sender_id, "help_btn_num", str(button_num))
            await set_step(event.sender_id, "help_btn_set_text")
            await event.edit(
                f"📝 **تنظیم دکمه {button_num}**\n\nمتن دکمه را ارسال کنید:",
                buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
            )
        return

    if data.startswith("help_btn_color:"):
        parts = data.split(":")
        button_num = int(parts[1])
        style_val = parts[2]
        help_crud = HelpButtonCRUD()
        if style_val == "none":
            await help_crud.set_button(button_num, button_style="")
            await event.answer("رنگ دکمه حذف شد.")
        else:
            await help_crud.set_button(button_num, button_style=style_val)
            await event.answer(f"رنگ تغییر کرد به {STYLE_LABELS.get(style_val, style_val)}.")
        return

    if data.startswith("help_btn_icon:"):
        button_num = int(data.split(":")[1])
        await set_data(event.sender_id, "help_btn_num", str(button_num))
        await set_step(event.sender_id, "help_btn_set_icon")
        await event.edit(
            "📎 آیدی سند ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
        )
        return

    if data.startswith("help_btn_icon_clear:"):
        button_num = int(data.split(":")[1])
        help_crud = HelpButtonCRUD()
        await help_crud.set_button(button_num, clear_icon=True)
        btn = await help_crud.get_button(button_num)
        await event.answer("آیکون دکمه حذف شد.")
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                f"📝 **دکمه {button_num}**\n{btn.button_text if btn else ''}\n\nانتخاب کنید:",
                buttons=create_help_button_submenu(button_num),
            )
        return

    if data.startswith("help_btn_edit_text:"):
        button_num = int(data.split(":")[1])
        await set_data(event.sender_id, "help_btn_num", str(button_num))
        await set_step(event.sender_id, "help_btn_edit_text")
        await event.edit(
            f"✏️ متن جدید برای دکمه {button_num} را ارسال کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
        )
        return

    if data.startswith("help_btn_edit_link:"):
        button_num = int(data.split(":")[1])
        await set_data(event.sender_id, "help_btn_num", str(button_num))
        await set_step(event.sender_id, "help_btn_edit_link")
        await event.edit(
            f"🔗 لینک جدید برای دکمه {button_num} را ارسال کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_help_config")]],
        )
        return

    if data.startswith("help_btn_delete:"):
        button_num = int(data.split(":")[1])
        help_crud = HelpButtonCRUD()
        success = await help_crud.delete_button(button_num)

        if success:
            buttons = await create_help_buttons_config_ui(back_data="back_to_help_settings")
            await event.edit("✅ دکمه حذف شد.", buttons=buttons)
        else:
            await event.answer("❌ خطا در حذف", alert=True)
        return

    if data.startswith("help_btn_style:"):
        style_val = data.split(":")[1]
        button_num_data = await get_data(event.sender_id, "help_btn_num")
        button_text_data = await get_data(event.sender_id, "help_btn_text")
        button_url_data = await get_data(event.sender_id, "help_btn_url")

        if not all([button_num_data, button_text_data, button_url_data]):
            await event.answer("❌ خطا: اطلاعات دکمه یافت نشد.", alert=True)
            return

        button_num = int(button_num_data)
        help_crud = HelpButtonCRUD()

        if style_val != "skip":
            await help_crud.set_button(button_num, button_style=style_val)

        await delete_data(event.sender_id, "help_btn_num")
        await delete_data(event.sender_id, "help_btn_text")
        await delete_data(event.sender_id, "help_btn_url")
        await set_step(event.sender_id, "home")
        buttons = await create_help_buttons_config_ui(back_data="back_to_help_settings")
        await event.edit(f"✅ دکمه {button_num} تنظیم شد.", buttons=buttons)
        return

    if data == "back_to_help_config":
        await delete_data(event.sender_id, "help_btn_num")
        await delete_data(event.sender_id, "help_btn_text")
        await delete_data(event.sender_id, "help_btn_url")
        await set_step(event.sender_id, "home")

        buttons = await create_help_buttons_config_ui(back_data="back_to_help_settings")
        await event.edit(
            "✏️ **دکمه‌های لینک**\n\nروی هر مورد کلیک → متن، لینک، رنگ، آیکون.",
            buttons=buttons,
        )
        return
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        callback_settings_menu_page,
        events.CallbackQuery(pattern=states.SETTINGS_MENU_PATTERN, func=lambda e: e.sender_id in ADMIN_ID),
    )
    client.add_event_handler(callback_settings_toggle, events.CallbackQuery(func=settings_callback_filter))
    client.add_event_handler(callback_settings_admin, events.CallbackQuery(func=settings_admin_callback_filter))

"""Callback handlers for admin panel management flow."""

from __future__ import annotations

import contextlib

from httpx import HTTPStatusError
from telethon import Button, events
from telethon.errors.rpcerrorlist import MessageNotModifiedError

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.panels.auth import (
    AUTH_API_KEY,
    create_panel_api,
    format_exception_message,
    panel_api_error_text,
    panel_uses_api_key,
    refresh_panel_cookie,
)
from app.services.panels.config_links import (
    summarize_single_config_link_selection,
)
from app.services.panels.groups import (
    build_add_panel_group_message,
    build_change_panel_group_message,
    build_group_selection_buttons,
    cache_panel_groups,
    clear_cached_panel_groups,
    create_panel_with_group,
    fetch_panel_groups,
    get_add_panel_groups_from_redis,
    get_cached_panel_groups,
    group_ids_to_step_data,
    serialize_group_ids,
    step_data_to_group_ids,
    summarize_selected_groups,
)
from app.services.panels.settings import (
    delete_time_plan_from_feature_settings,
    delete_volume_plan_from_feature_settings,
    get_panel_time_plan,
    get_panel_volume_plan,
    is_custom_buy_ready,
    is_reseller_capacity_ready,
    panel_button_enabled,
    panel_custom_buy_settings,
    panel_default_group_ids,
    panel_display_mode,
    panel_node_prefixes,
    panel_renew_volume_remaining_mode,
    panel_reseller_button_settings,
    panel_reseller_capacity_settings,
    panel_reseller_sale_flag,
    panel_shop_sale_flag,
    panel_show_prefixes_in_locations,
    panel_single_config_link_indexes,
    panel_user_limit,
    panel_webhook_notifications_enabled,
    subscription_settings,
    toggle_custom_buy_enabled,
    toggle_panel_reseller_button_setting,
    toggle_panel_sales_setting,
    toggle_reseller_capacity_enabled,
    update_time_plan_in_feature_settings,
    update_volume_plan_in_feature_settings,
)
from app.services.subscriptions.links import resolve_subscription_link_mode
from app.telegram.admin.discounts import show_discount_codes
from app.telegram.admin.panels import states
from app.telegram.admin.panels.service import (
    build_panel_summary_block,
    build_panel_test_settings_content,
    display_panels,
    mutate_panel_feature_settings,
    show_panel_custom_buy_menu,
    show_panel_ms_buttons_menu,
    show_panel_reseller_capacity_menu,
    show_panel_time_plans_menu,
    show_panel_volume_plans_menu,
    update_panel_buttons,
)
from app.telegram.keyboards.admin import panel_xui_buttons
from app.telegram.keyboards.registry import STYLE_LABELS
from app.telegram.shared.keyboards.panel_buttons import (
    PANEL_MS_BUTTON_TOGGLES,
    PANEL_MS_RESELLER_BUTTON_TOGGLES,
    build_panel_time_plan_info_buttons,
    build_panel_volume_plan_info_buttons,
    create_panel_display_config_submenu,
    create_time_plan_display_config_submenu,
    create_volume_plan_display_config_submenu,
    default_time_upgrade_button_text,
    default_volume_upgrade_button_text,
    ensure_panel_display_record,
    panel_display_config_text,
    panel_display_keyboard_key,
    panel_time_plan_info_text,
    panel_volume_plan_info_text,
    time_plan_display_config_text,
    volume_plan_display_config_text,
)
from app.telegram.shared.messages.panel_settings_help import (
    build_panel_settings_help_buttons,
    build_panel_settings_help_text,
)
from app.telegram.state import get_data, get_step, set_data, set_step
from app.telegram.state.store import clear_user_conversation, get_user_state, set_user_state
from config import ADMIN_ID

logger = get_logger(__name__)


def panel_admin_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    try:
        data = event.data.decode("utf-8")
    except Exception:
        return False
    if data in states.PANEL_ADMIN_EXACT:
        return True
    return any(data.startswith(p) for p in states.PANEL_ADMIN_PREFIXES)


async def panel_admin_callback_handler(event: events.CallbackQuery.Event):
    if not event.is_private:
        return
    data = event.data.decode("UTF-8")
    if data.startswith("panel_info:"):
        panel_id = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_id)

        if panel:
            info_string = build_panel_summary_block(panel)

            try:
                if not panel.cookie:
                    raise ValueError("کوکی نامعتبر است یا وجود ندارد.")

                api = create_panel_api(panel)
                system_stats = await api.get_system_stats(admin_username=panel.username)

                server_status = (
                    "┄┄<b>وضعیت سرور</b>┄┄\n"
                    f"🔖 <b>نسخه:</b> {system_stats.version}\n"
                    f"🧠 <b>مجموع رم:</b> {round(system_stats.mem_total / (1024**3), 2)} گیگ\n"
                    f"📊 <b>رم استفاده‌شده:</b> {round(system_stats.mem_used / (1024**3), 2)} گیگ\n"
                    f"🧩 <b>تعداد هسته سی‌پی‌یو:</b> {system_stats.cpu_cores}\n"
                    f"📉 <b>درصد استفاده سی‌پی‌یو:</b> {system_stats.cpu_usage}%\n"
                    f"👤 <b>تعداد کل کاربران:</b> {system_stats.total_user}\n"
                    f"🟢 <b>کاربران آنلاین:</b> {system_stats.online_users}\n"
                    f"✅ <b>کاربران فعال:</b> {system_stats.active_users}\n"
                    f"⏸️ <b>کاربران آن‌هولد:</b> {system_stats.on_hold_users}\n"
                    f"🚫 <b>کاربران غیرفعال:</b> {system_stats.disabled_users}\n"
                    f"📆 <b>کاربران تاریخ‌گذشته:</b> {system_stats.expired_users}\n"
                    f"📉 <b>کاربران دارای محدودیت:</b> {system_stats.limited_users}\n"
                    f"📥 <b>دانلود کل:</b> {round(system_stats.incoming_bandwidth / (1024**3), 2)} گیگ\n"
                    f"📤 <b>آپلود کل:</b> {round(system_stats.outgoing_bandwidth / (1024**3), 2)} گیگ\n"
                )

            except Exception as e:
                error_message = str(e)
                if "401 Unauthorized" in error_message and not panel_uses_api_key(panel):
                    try:
                        await refresh_panel_cookie(panel)
                        server_status = "┄┄<b>وضعیت سرور</b>┄┄\n✅ کوکی جدید دریافت شد."
                    except Exception as e2:
                        server_status = f"خطا در بازیابی کوکی جدید: {e2!s}"
                else:
                    server_status = f"خطا در دریافت وضعیت سرور: {error_message}"

            await update_panel_buttons(event, panel, info_string, server_status)

            await event.answer(f"جزئیات پنل: {panel.base_url}")
            await set_step(event.sender_id, "ToPanel")
        else:
            await event.answer("پنل پیدا نشد!")

    elif data.startswith("edit_panel_display:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return

        btn_obj = await KeyboardButtonCRUD().get_button(panel_display_keyboard_key(panel_code))
        await set_data(event.sender_id, "edit_panel_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            panel_display_config_text(panel, btn_obj),
            buttons=create_panel_display_config_submenu(panel_code),
        )

    elif data.startswith("panel_display_edit_text:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return

        btn_obj = await KeyboardButtonCRUD().get_button(panel_display_keyboard_key(panel_code))
        current = btn_obj.button_text if btn_obj and btn_obj.button_text else panel.name
        await set_step(event.sender_id, f"edit_panel_display:{panel_code}")
        await set_data(event.sender_id, "edit_panel_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            f"📝 متن فعلی دکمه پنل:\n<blockquote expandable>{current}</blockquote>\n\n"
            "متن جدید را بفرستید یا /skip برای استفاده از نام پنل:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_panel_display:{panel_code}")]],
            parse_mode="html",
        )

    elif data.startswith("panel_display_color:"):
        parts = data.split(":")
        if len(parts) < 3:
            await event.answer("❌ درخواست نامعتبر", alert=True)
            return
        panel_code = int(parts[1])
        style_val = parts[2]

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        key = panel_display_keyboard_key(panel_code)
        await ensure_panel_display_record(panel)
        keyboard_crud = KeyboardButtonCRUD()
        if style_val == "none":
            await keyboard_crud.set_button(key, button_style="")
            await event.answer("رنگ حذف شد.")
        else:
            await keyboard_crud.set_button(key, button_style=style_val)
            await event.answer("رنگ ذخیره شد.")
        btn_obj = await keyboard_crud.get_button(key)
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                panel_display_config_text(panel, btn_obj),
                buttons=create_panel_display_config_submenu(panel_code),
            )

    elif data.startswith("panel_display_icon_clear:"):
        panel_code = int(data.split(":")[1])

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        key = panel_display_keyboard_key(panel_code)
        await ensure_panel_display_record(panel)
        await KeyboardButtonCRUD().set_button(key, clear_icon=True)
        await event.answer("آیکون حذف شد.")
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                panel_display_config_text(panel, btn_obj),
                buttons=create_panel_display_config_submenu(panel_code),
            )

    elif data.startswith("panel_display_icon:"):
        panel_code = int(data.split(":")[1])
        await set_data(event.sender_id, "panel_display_panel_code", str(panel_code))
        await set_step(event.sender_id, "panel_display_set_icon")
        await event.edit(
            "📎 آیدی ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_panel_display:{panel_code}")]],
        )

    elif data.startswith("panel_display_reset:"):
        panel_code = int(data.split(":")[1])

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        await KeyboardButtonCRUD().delete_button(panel_display_keyboard_key(panel_code))
        await event.answer("تنظیمات ریست شد.")
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                panel_display_config_text(panel, None),
                buttons=create_panel_display_config_submenu(panel_code),
            )

    if data.startswith("panel_add_auth:"):
        auth_type = data.split(":")[1]
        await set_user_state(event.sender_id, "auth_type", auth_type)
        if auth_type == AUTH_API_KEY:
            await set_step(event.sender_id, "AddPanel_api_key")
            await event.edit(
                "🔑 API Key پنل را ارسال کنید:",
                buttons=[[Button.inline("❌ انصراف", data="panel_add_group_cancel")]],
            )
        else:
            await set_step(event.sender_id, "AddPanel_username")
            await event.edit(
                "نام کاربری پنل را ارسال کنید:",
                buttons=[[Button.inline("❌ انصراف", data="panel_add_group_cancel")]],
            )

    elif data.startswith("panel_auth_type:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        await event.edit(
            f"🔐 تنظیمات ورود پنل «{panel.name}»\n\n"
            f"🌐 آدرس فعلی:\n`{panel.base_url}`\n\n"
            "نوع ورود را انتخاب کنید یا آدرس پنل را تغییر دهید:",
            buttons=[
                [Button.inline("🌐 تغییر آدرس پنل", data=f"change_panel_url:{panel_code}")],
                [Button.inline("👤 نام کاربری و رمز", data=f"panel_auth_set:password:{panel_code}")],
                [Button.inline("🔑 API Key", data=f"panel_auth_set:api_key:{panel_code}")],
                [Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")],
            ],
            parse_mode="markdown",
        )

    elif data.startswith("change_panel_url:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        await event.edit(
            f"🌐 آدرس فعلی پنل:\n`{panel.base_url}`\n\n"
            "آدرس جدید را ارسال کنید.\n"
            "〰️ مثال: `https://panel.example.com`\n"
            "〰️ اگر پنل روی پورت اختصاصی است: `https://panel.example.com:8000`\n\n"
            "⚠️ فقط دامنه یا آی‌پی (و در صورت نیاز پورت) را وارد کنید؛ بدون path.",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_auth_type:{panel_code}")]],
            parse_mode="markdown",
        )
        await set_step(event.sender_id, "ChangePanelUrl")
        await set_data(event.sender_id, "ChangePanelUrl", panel_code)

    elif data.startswith("panel_auth_set:"):
        parts = data.split(":")
        auth_kind = parts[1]
        panel_code = int(parts[2])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد!", alert=True)
            return
        await set_user_state(event.sender_id, "change_panel_auth_code", panel_code)
        if auth_kind == AUTH_API_KEY:
            await set_step(event.sender_id, "ChangePanelAuth_api_key")
            await event.edit(
                "🔑 API Key جدید را ارسال کنید:",
                buttons=[[Button.inline("❌ انصراف", data=f"panel_auth_type:{panel_code}")]],
            )
        else:
            await set_step(event.sender_id, "ChangePanelAuth_username")
            await event.edit(
                "نام کاربری جدید پنل را ارسال کنید:",
                buttons=[[Button.inline("❌ انصراف", data=f"panel_auth_type:{panel_code}")]],
            )

    if data.startswith("panel_add_group_toggle:"):
        if await get_step(event.sender_id) != "AddPanel_select_group":
            await event.answer("فرآیند افزودن پنل فعال نیست.", alert=True)
            return
        try:
            group_id = int(data.split(":")[1])
        except IndexError, ValueError:
            await event.answer("شناسه گروه نامعتبر است.", alert=True)
            return

        groups = await get_add_panel_groups_from_redis(event.sender_id)
        if not groups:
            await event.answer("لیست گروه‌ها در دسترس نیست. لطفاً دوباره تلاش کن.", alert=True)
            return

        selected = step_data_to_group_ids(await get_user_state(event.sender_id, "panel_selected_groups"))
        if group_id in selected:
            selected.remove(group_id)
        else:
            selected.append(group_id)

        await set_user_state(event.sender_id, "panel_selected_groups", selected)

        message = build_add_panel_group_message(groups, selected)
        buttons = build_group_selection_buttons(
            groups,
            selected,
            lambda gid: f"panel_add_group_toggle:{gid}",
            "panel_add_group_confirm",
            "panel_add_group_cancel",
            "panel_add_group_select_all",
        )
        await event.edit(message, buttons=buttons)

    elif data == "panel_add_group_select_all":
        if await get_step(event.sender_id) != "AddPanel_select_group":
            await event.answer("فرآیند افزودن پنل فعال نیست.", alert=True)
            return

        groups = await get_add_panel_groups_from_redis(event.sender_id)
        if not groups:
            await event.answer("لیست گروه‌ها در دسترس نیست. لطفاً دوباره تلاش کن.", alert=True)
            return

        await set_user_state(event.sender_id, "panel_selected_groups", [])

        message = build_add_panel_group_message(groups, [])
        buttons = build_group_selection_buttons(
            groups,
            [],
            lambda gid: f"panel_add_group_toggle:{gid}",
            "panel_add_group_confirm",
            "panel_add_group_cancel",
            "panel_add_group_select_all",
        )
        await event.edit(message, buttons=buttons)

    elif data == "panel_add_group_confirm":
        if await get_step(event.sender_id) != "AddPanel_select_group":
            await event.answer("فرآیند افزودن پنل فعال نیست.", alert=True)
            return

        groups = await get_add_panel_groups_from_redis(event.sender_id)
        selected = step_data_to_group_ids(await get_user_state(event.sender_id, "panel_selected_groups"))
        selected_ids = selected if selected else None

        try:
            new_panel, group_name = await create_panel_with_group(event.sender_id, selected_ids)
            await event.edit(
                f"پنل {new_panel.name} با موفقیت ذخیره شد.\nگروه پیش‌فرض کاربران: {group_name}",
                buttons=panel_xui_buttons,
            )
        except ValueError as e:
            await event.answer(str(e), alert=True)
        except Exception as e:
            detail = format_exception_message(e)
            await clear_user_conversation(event.sender_id)
            await set_step(event.sender_id, "panel")
            await event.edit(panel_api_error_text(e), buttons=panel_xui_buttons)
            logger.exception("Add panel confirm error: %s", detail)
        finally:
            clear_cached_panel_groups("add", event.sender_id)

    elif data == "panel_add_group_cancel":
        clear_cached_panel_groups("add", event.sender_id)
        await clear_user_conversation(event.sender_id)
        await set_step(event.sender_id, "panel")
        await event.edit("افزودن پنل لغو شد.", buttons=panel_xui_buttons)

    elif data.startswith("change_panel_group:"):
        panel_id = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_id)
        if not panel:
            await event.answer("پنل پیدا نشد.", alert=True)
            return
        try:
            groups_resp = await fetch_panel_groups(panel)
        except HTTPStatusError as e:
            await event.answer(f"HTTP error occurred: {e}", alert=True)
            return

        groups_data = [(group.id, group.name) for group in groups_resp.groups]
        selected_ids = sorted(
            {gid for gid in panel_default_group_ids(panel) if any(gid == gid_item for gid_item, _ in groups_data)}
        )

        cache_panel_groups("change", event.sender_id, groups_data, panel.code)
        await set_data(event.sender_id, "panel_change_target", str(panel.code))
        await set_data(event.sender_id, "panel_change_selected", group_ids_to_step_data(selected_ids))

        message = build_change_panel_group_message(groups_data, selected_ids)
        buttons = build_group_selection_buttons(
            groups_data,
            selected_ids,
            lambda gid: f"panel_update_group_toggle:{panel.code}:{gid}",
            f"panel_update_group_confirm:{panel.code}",
            f"panel_update_group_cancel:{panel.code}",
            f"panel_update_group_select_all:{panel.code}",
        )
        await event.edit(message, buttons=buttons)
    elif data.startswith("panel_update_group_toggle:"):
        try:
            _, panel_id_str, group_id_str = data.split(":")
            panel_code = int(panel_id_str)
            group_id = int(group_id_str)
        except ValueError, IndexError:
            await event.answer("شناسه نامعتبر است.", alert=True)
            return

        target = await get_data(event.sender_id, "panel_change_target")
        if not target or int(target) != panel_code:
            await event.answer("این عملیات منقضی شده است. دوباره تلاش کن.", alert=True)
            return

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد.", alert=True)
            return

        groups = get_cached_panel_groups("change", event.sender_id, panel_code)
        if not groups:
            try:
                groups_resp = await fetch_panel_groups(panel)
            except HTTPStatusError as e:
                await event.answer(f"HTTP error occurred: {e}", alert=True)
                return
            groups = [(group.id, group.name) for group in groups_resp.groups]
            cache_panel_groups("change", event.sender_id, groups, panel_code)

        selected = step_data_to_group_ids(await get_data(event.sender_id, "panel_change_selected"))
        if group_id in selected:
            selected.remove(group_id)
        else:
            selected.append(group_id)

        await set_data(event.sender_id, "panel_change_selected", group_ids_to_step_data(selected))

        message = build_change_panel_group_message(groups, selected)
        buttons = build_group_selection_buttons(
            groups,
            selected,
            lambda gid: f"panel_update_group_toggle:{panel_code}:{gid}",
            f"panel_update_group_confirm:{panel_code}",
            f"panel_update_group_cancel:{panel_code}",
            f"panel_update_group_select_all:{panel_code}",
        )
        await event.edit(message, buttons=buttons)

    elif data.startswith("panel_update_group_select_all:"):
        try:
            panel_code = int(data.split(":")[1])
        except ValueError, IndexError:
            await event.answer("شناسه نامعتبر است.", alert=True)
            return

        target = await get_data(event.sender_id, "panel_change_target")
        if not target or int(target) != panel_code:
            await event.answer("این عملیات منقضی شده است. دوباره تلاش کن.", alert=True)
            return

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد.", alert=True)
            return

        groups = get_cached_panel_groups("change", event.sender_id, panel_code)
        if not groups:
            try:
                groups_resp = await fetch_panel_groups(panel)
            except HTTPStatusError as e:
                await event.answer(f"HTTP error occurred: {e}", alert=True)
                return
            groups = [(group.id, group.name) for group in groups_resp.groups]
            cache_panel_groups("change", event.sender_id, groups, panel_code)

        await set_data(event.sender_id, "panel_change_selected", "")

        message = build_change_panel_group_message(groups, [])
        buttons = build_group_selection_buttons(
            groups,
            [],
            lambda gid: f"panel_update_group_toggle:{panel_code}:{gid}",
            f"panel_update_group_confirm:{panel_code}",
            f"panel_update_group_cancel:{panel_code}",
            f"panel_update_group_select_all:{panel_code}",
        )
        await event.edit(message, buttons=buttons)

    elif data.startswith("panel_update_group_confirm:"):
        try:
            panel_code = int(data.split(":")[1])
        except ValueError, IndexError:
            await event.answer("شناسه نامعتبر است.", alert=True)
            return

        target = await get_data(event.sender_id, "panel_change_target")
        if not target or int(target) != panel_code:
            await event.answer("این عملیات منقضی شده است. دوباره تلاش کن.", alert=True)
            return

        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل پیدا نشد.", alert=True)
            return

        groups = get_cached_panel_groups("change", event.sender_id, panel_code)
        if not groups:
            try:
                groups_resp = await fetch_panel_groups(panel)
            except HTTPStatusError as e:
                await event.answer(f"HTTP error occurred: {e}", alert=True)
                return
            groups = [(group.id, group.name) for group in groups_resp.groups]
            cache_panel_groups("change", event.sender_id, groups, panel_code)

        selected = step_data_to_group_ids(await get_data(event.sender_id, "panel_change_selected"))
        storage_value = serialize_group_ids(selected if selected else None)
        await PanelsManager().update_panel(panel.code, default_group_ids=storage_value)
        panel.default_group_ids = storage_value

        summary = summarize_selected_groups(groups, selected)
        await event.edit(
            f"گروه پیش‌فرض کاربران به {summary} تغییر کرد.",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_info:{panel.code}")]],
        )

        await set_data(event.sender_id, "panel_change_target", "")
        await set_data(event.sender_id, "panel_change_selected", "")
        clear_cached_panel_groups("change", event.sender_id, panel_code)

    elif data.startswith("panel_update_group_cancel:"):
        try:
            panel_code = int(data.split(":")[1])
        except ValueError, IndexError:
            await event.answer("شناسه نامعتبر است.", alert=True)
            return

        await set_data(event.sender_id, "panel_change_target", "")
        await set_data(event.sender_id, "panel_change_selected", "")
        clear_cached_panel_groups("change", event.sender_id, panel_code)
        await event.edit(
            "تغییر گروه پیش‌فرض لغو شد.", buttons=[[Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")]]
        )

    elif data.startswith("panel_toggle_status:"):
        panel_code = data.split(":")[1]

        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        info_string = "<b>┄┄مشخصات پنل┄┄</b>\n"
        info_string += f"<b>اسم پنل:</b> {panel.name}\n"
        info_string += f"<b>کدپنل:</b> {panel.code}\n"
        info_string += f"<b>وضعیت:</b> {panel.enable}\n"
        info_string += f"<b>آدرس پنل:</b> {panel.base_url}\n"
        info_string += f"<b>لینک تانل:</b> {panel.tunnel_url}\n"

        server_status = "وضعیت سرور در حال بررسی است..."

        panel.enable = not panel.enable
        await panel_manager.update_panel(panel_code, enable=panel.enable)

        await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_toggle_shop_sale:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()

        def _toggle_shop(settings):
            toggle_panel_sales_setting(settings, "shop_enabled")

        if not await mutate_panel_feature_settings(panel_code, _toggle_shop):
            await event.answer("❌ خطا در ذخیره تنظیمات.", alert=True)
            return
        panel = await panel_manager.get_panel_by_code(panel_code)
        status_text = "فعال ✅" if panel_shop_sale_flag(panel) else "غیرفعال ❌"
        await event.answer(f"🛒 خرید سرویس: {status_text}", alert=False)
        await update_panel_buttons(
            event,
            panel,
            build_panel_summary_block(panel),
            "وضعیت سرور در حال بررسی است...",
        )

    elif data.startswith("panel_toggle_reseller_sale:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()

        def _toggle_reseller(settings):
            toggle_panel_sales_setting(settings, "reseller_enabled")

        if not await mutate_panel_feature_settings(panel_code, _toggle_reseller):
            await event.answer("❌ خطا در ذخیره تنظیمات.", alert=True)
            return
        panel = await panel_manager.get_panel_by_code(panel_code)
        status_text = "فعال ✅" if panel_reseller_sale_flag(panel) else "غیرفعال ❌"
        await event.answer(f"🏢 نمایندگی: {status_text}", alert=False)
        await update_panel_buttons(
            event,
            panel,
            build_panel_summary_block(panel),
            "وضعیت سرور در حال بررسی است...",
        )

    elif data.startswith("panel_user_limit:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            current_services = await panel_manager.count_panel_users(panel_code)
            current_limit = panel_user_limit(panel) or "نامحدود"

            buttons = [
                [Button.inline("🔢 تعیین محدودیت جدید", data=f"set_user_limit:{panel_code}")],
                [Button.inline("♾️ نامحدود کردن", data=f"unlimited_users:{panel_code}")],
                [Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")],
            ]

            await event.edit(
                f"**🔢 مدیریت محدودیت کانفیگ پنل {panel.name}**\n\n"
                f"📊 تعداد کانفیگ‌های فعلی: `{current_services}`\n"
                f"🎯 محدودیت تنظیم شده: `{current_limit}`\n\n"
                f"💡 با تنظیم محدودیت، وقتی تعداد کانفیگ‌ها به این عدد برسد، پنل در لیست خرید نمایش داده نمی‌شود.",
                buttons=buttons,
            )

    elif data.startswith("set_user_limit:"):
        panel_code = int(data.split(":")[1])
        await set_data(event.sender_id, "panel_user_limit_code", panel_code)
        await set_step(event.sender_id, "waiting_user_limit")

        await event.edit(
            "🔢 **تنظیم محدودیت تعداد کانفیگ**\n\n"
            "لطفاً حداکثر تعداد کانفیگ‌های مجاز برای این پنل را وارد کنید:\n\n"
            "مثال: 100\n"
            "⚠️ فقط عدد صحیح مثبت وارد کنید.",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_info:{panel_code}")]],
        )

    elif data.startswith("unlimited_users:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        await panel_manager.update_panel(panel_code, user_limit=None)

        panel = await panel_manager.get_panel_by_code(panel_code)
        await event.answer("✅ محدودیت کانفیگ به نامحدود تغییر یافت!", alert=True)

        current_services = await panel_manager.count_panel_users(panel_code)
        buttons = [
            [Button.inline("🔢 تعیین محدودیت جدید", data=f"set_user_limit:{panel_code}")],
            [Button.inline("♾️ نامحدود کردن", data=f"unlimited_users:{panel_code}")],
            [Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")],
        ]

        await event.edit(
            f"**🔢 مدیریت محدودیت کانفیگ پنل {panel.name}**\n\n"
            f"📊 تعداد کانفیگ‌های فعلی: `{current_services}`\n"
            f"🎯 محدودیت تنظیم شده: `نامحدود`\n\n"
            f"💡 با تنظیم محدودیت، وقتی تعداد کانفیگ‌ها به این عدد برسد، پنل در لیست خرید نمایش داده نمی‌شود.",
            buttons=buttons,
        )

    elif data.startswith("panel_btn_zaman:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            new_status = not panel_button_enabled(panel, "btn_zaman")
            await panel_manager.update_panel(panel_code, btn_zaman=new_status)
            panel = await panel_manager.get_panel_by_code(panel_code)

            status_text = "فعال ✅" if new_status else "غیرفعال ❌"
            await event.answer(f"✅ وضعیت خرید زمان به {status_text} تغییر یافت!", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_btn_hajm:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            new_status = not panel_button_enabled(panel, "btn_hajm")
            await panel_manager.update_panel(panel_code, btn_hajm=new_status)
            panel = await panel_manager.get_panel_by_code(panel_code)

            status_text = "فعال ✅" if new_status else "غیرفعال ❌"
            await event.answer(f"✅ وضعیت خرید حجم به {status_text} تغییر یافت!", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_ms_buttons:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await show_panel_ms_buttons_menu(event, panel)
        await event.answer()

    elif data.startswith("panel_ms_btn:"):
        parts = data.split(":")
        if len(parts) != 3:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        btn_key, panel_code_str = parts[1], parts[2]
        toggle_map = {key: (attr, label) for key, attr, label in PANEL_MS_BUTTON_TOGGLES}
        toggle = toggle_map.get(btn_key)
        if not toggle:
            await event.answer("❌ دکمه نامعتبر است.", alert=True)
            return
        attr, label = toggle
        panel_code = int(panel_code_str)
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        current = panel_button_enabled(panel, attr)
        new_status = not current
        await panel_manager.update_panel(panel_code, **{attr: new_status})
        panel = await panel_manager.get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        status_text = "فعال ✅" if new_status else "غیرفعال ❌"
        await event.answer(f"✅ {label} به {status_text} تغییر یافت!", alert=True)
        await show_panel_ms_buttons_menu(event, panel)

    elif data.startswith("panel_ms_reseller_header:"):
        await event.answer("دکمه‌های نمایندگی جدا از دکمه‌های سرویس ذخیره می‌شوند.", alert=True)

    elif data.startswith("panel_ms_reseller_btn:"):
        parts = data.split(":")
        if len(parts) != 3:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        btn_key, panel_code_str = parts[1], parts[2]
        toggle_map = dict(PANEL_MS_RESELLER_BUTTON_TOGGLES)
        label = toggle_map.get(btn_key)
        if not label:
            await event.answer("❌ دکمه نمایندگی نامعتبر است.", alert=True)
            return
        panel_code = int(panel_code_str)

        def _toggle_reseller_button(settings):
            toggle_panel_reseller_button_setting(settings, btn_key)

        if not await mutate_panel_feature_settings(panel_code, _toggle_reseller_button):
            await event.answer("❌ خطا در ذخیره تنظیمات.", alert=True)
            return

        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        new_status = next(value for key, value in panel_reseller_button_settings(panel).items() if key == btn_key)
        status_text = "فعال ✅" if new_status else "غیرفعال ❌"
        await event.answer(f"✅ {label} به {status_text} تغییر یافت!", alert=True)
        await show_panel_ms_buttons_menu(event, panel)

    elif data.startswith("panel_custom_buy:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await show_panel_custom_buy_menu(event, panel)

    elif data.startswith("panel_custom_buy_toggle:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        if not await mutate_panel_feature_settings(panel_code, toggle_custom_buy_enabled):
            await event.answer("❌ خطا در ذخیره تنظیمات.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        settings = panel_custom_buy_settings(panel)
        ready = is_custom_buy_ready(settings)
        if settings["enabled"] and not ready:
            await event.answer("⚠️ روشن شد؛ برای فعال‌سازی نهایی نرخ هر گیگ و هر روز را تنظیم کنید.", alert=True)
        else:
            await event.answer(
                f"✅ خرید دلخواه {'فعال' if ready else 'غیرفعال'} شد.",
                alert=True,
            )
        await show_panel_custom_buy_menu(event, panel)

    elif data.startswith("panel_custom_buy_price_gb:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        settings = panel_custom_buy_settings(panel)
        await set_data(event.sender_id, "panel_custom_buy_code", str(panel_code))
        await set_step(event.sender_id, "waiting_custom_buy_price_gb")
        await event.edit(
            "💰 **تنظیم قیمت هر گیگ (خرید دلخواه)**\n\n"
            f"پنل: `{panel.name}`\n"
            f"نرخ فعلی: `{settings['price_per_gb']:,}` تومان\n\n"
            "قیمت هر گیگ را به تومان وارد کنید.\n"
            "مثال: `5000`",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_custom_buy:{panel_code}")]],
        )

    elif data.startswith("panel_custom_buy_price_day:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        settings = panel_custom_buy_settings(panel)
        await set_data(event.sender_id, "panel_custom_buy_code", str(panel_code))
        await set_step(event.sender_id, "waiting_custom_buy_price_day")
        await event.edit(
            "⏰ **تنظیم قیمت هر روز (خرید دلخواه)**\n\n"
            f"پنل: `{panel.name}`\n"
            f"نرخ فعلی: `{settings['price_per_day']:,}` تومان\n\n"
            "قیمت هر روز را به تومان وارد کنید.\n"
            "مثال: `1000`",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_custom_buy:{panel_code}")]],
        )

    elif data.startswith("panel_reseller_capacity_toggle:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        if not await mutate_panel_feature_settings(panel_code, toggle_reseller_capacity_enabled):
            await event.answer("❌ خطا در ذخیره تنظیمات.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        settings = panel_reseller_capacity_settings(panel)
        ready = is_reseller_capacity_ready(settings)
        if settings["enabled"] and not ready:
            await event.answer("⚠️ روشن شد؛ برای فعال‌سازی نهایی قیمت هر کاربر را تنظیم کنید.", alert=True)
        else:
            await event.answer(
                f"✅ خرید ظرفیت کاربر {'فعال' if ready else 'غیرفعال'} شد.",
                alert=True,
            )
        await show_panel_reseller_capacity_menu(event, panel)

    elif data.startswith("panel_reseller_capacity_price:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        settings = panel_reseller_capacity_settings(panel)
        await set_data(event.sender_id, "panel_reseller_capacity_code", str(panel_code))
        await set_step(event.sender_id, "waiting_reseller_capacity_price")
        await event.edit(
            "💰 **تنظیم قیمت هر کاربر (خرید ظرفیت نمایندگی)**\n\n"
            f"نرخ فعلی: `{settings['price_per_user']:,}` تومان\n\n"
            "قیمت هر کاربر اضافه را به تومان وارد کنید.\n"
            "مثال: `2000`",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_reseller_capacity:{panel_code}")]],
        )

    elif data.startswith("panel_reseller_capacity:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await show_panel_reseller_capacity_menu(event, panel)

    elif data.startswith("panel_volume_plans:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await show_panel_volume_plans_menu(event, panel)

    elif data.startswith("panel_time_plans:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await show_panel_time_plans_menu(event, panel)

    elif data.startswith("panel_add_volume_plan:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await set_step(event.sender_id, f"add_volume_plan_storage:{panel_code}")
        await event.edit(
            f"➕ **افزودن پلن حجم — {panel.name}**\n\nحجم را به گیگابایت وارد کنید.\nمثال: `10` یا `0.5`",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_volume_plans:{panel_code}")]],
        )

    elif data.startswith("panel_add_time_plan:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await set_step(event.sender_id, f"add_time_plan_duration:{panel_code}")
        await event.edit(
            f"➕ **افزودن پلن زمان — {panel.name}**\n\nمدت را به روز وارد کنید.\nمثال: `30`",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_time_plans:{panel_code}")]],
        )

    elif data.startswith("panel_volume_plan:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        plan_id = int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.edit(
            panel_volume_plan_info_text(panel, plan),
            buttons=build_panel_volume_plan_info_buttons(panel_code, plan_id),
        )

    elif data.startswith("panel_time_plan:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        plan_id = int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.edit(
            panel_time_plan_info_text(panel, plan),
            buttons=build_panel_time_plan_info_buttons(panel_code, plan_id),
        )

    elif data.startswith("panel_edit_volume_storage:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_step(event.sender_id, f"edit_volume_plan_storage:{panel_code}:{plan_id}")
        await event.edit(
            "💾 حجم جدید را به گیگابایت وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_volume_plan:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("panel_edit_volume_price:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_step(event.sender_id, f"edit_volume_plan_price:{panel_code}:{plan_id}")
        await event.edit(
            "💰 قیمت جدید را به تومان وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_volume_plan:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("panel_edit_time_duration:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_step(event.sender_id, f"edit_time_plan_duration:{panel_code}:{plan_id}")
        await event.edit(
            "📅 مدت جدید را به روز وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_time_plan:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("panel_edit_time_price:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_step(event.sender_id, f"edit_time_plan_price:{panel_code}:{plan_id}")
        await event.edit(
            "💰 قیمت جدید را به تومان وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_time_plan:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("panel_delete_volume_plan:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _delete_volume(settings):
            delete_volume_plan_from_feature_settings(settings, plan_id)

        if await mutate_panel_feature_settings(panel_code, _delete_volume):
            await event.answer("✅ پلن حجم حذف شد.")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            if panel:
                await show_panel_volume_plans_menu(event, panel)
        else:
            await event.answer("❌ خطا در حذف.", alert=True)

    elif data.startswith("panel_delete_time_plan:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _delete_time(settings):
            delete_time_plan_from_feature_settings(settings, plan_id)

        if await mutate_panel_feature_settings(panel_code, _delete_time):
            await event.answer("✅ پلن زمان حذف شد.")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            if panel:
                await show_panel_time_plans_menu(event, panel)
        else:
            await event.answer("❌ خطا در حذف.", alert=True)

    elif data.startswith("edit_volume_plan_display:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await set_data(event.sender_id, "edit_volume_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            volume_plan_display_config_text(panel, plan),
            buttons=create_volume_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("edit_time_plan_display:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await set_data(event.sender_id, "edit_time_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            time_plan_display_config_text(panel, plan),
            buttons=create_time_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("volume_plan_btn_edit_text:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        custom = (plan.get("display_button_text") or "").strip()
        tpl = custom if custom else "{gig} گیگ — {price} تومان"
        preview = default_volume_upgrade_button_text(plan)
        await set_step(event.sender_id, f"edit_volume_plan_display:{panel_code}:{plan_id}")
        await set_data(event.sender_id, "edit_volume_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            f"پلیس‌هولدرها: <code>{{gig}}</code> <code>{{price}}</code>\n\n"
            f"قالب: <blockquote expandable>{tpl}</blockquote>\n"
            f"پیش‌نمایش: <blockquote expandable>{preview}</blockquote>\n\n"
            "متن جدید یا /skip:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_volume_plan_display:{panel_code}:{plan_id}")]],
            parse_mode="html",
        )

    elif data.startswith("time_plan_btn_edit_text:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id) if panel else None
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        custom = (plan.get("display_button_text") or "").strip()
        tpl = custom if custom else "{days} روز — {price} تومان"
        preview = default_time_upgrade_button_text(plan)
        await set_step(event.sender_id, f"edit_time_plan_display:{panel_code}:{plan_id}")
        await set_data(event.sender_id, "edit_time_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            f"پلیس‌هولدرها: <code>{{days}}</code> <code>{{price}}</code>\n\n"
            f"قالب: <blockquote expandable>{tpl}</blockquote>\n"
            f"پیش‌نمایش: <blockquote expandable>{preview}</blockquote>\n\n"
            "متن جدید یا /skip:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_time_plan_display:{panel_code}:{plan_id}")]],
            parse_mode="html",
        )

    elif data.startswith("volume_plan_btn_color:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        panel_code, plan_id, style_val = int(parts[1]), int(parts[2]), parts[3]
        style = "" if style_val == "none" else style_val

        def _set_style(settings):
            update_volume_plan_in_feature_settings(
                settings,
                plan_id,
                button_style=style,
                set_button_style=True,
            )

        if not await mutate_panel_feature_settings(panel_code, _set_style):
            await event.answer("❌ خطا در ذخیره.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer(
            "رنگ دکمه حذف شد." if style_val == "none" else f"رنگ تغییر کرد به {STYLE_LABELS.get(style_val, style_val)}."
        )
        await event.edit(
            volume_plan_display_config_text(panel, plan),
            buttons=create_volume_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("time_plan_btn_color:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        panel_code, plan_id, style_val = int(parts[1]), int(parts[2]), parts[3]
        style = "" if style_val == "none" else style_val

        def _set_style(settings):
            update_time_plan_in_feature_settings(
                settings,
                plan_id,
                button_style=style,
                set_button_style=True,
            )

        if not await mutate_panel_feature_settings(panel_code, _set_style):
            await event.answer("❌ خطا در ذخیره.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer(
            "رنگ دکمه حذف شد." if style_val == "none" else f"رنگ تغییر کرد به {STYLE_LABELS.get(style_val, style_val)}."
        )
        await event.edit(
            time_plan_display_config_text(panel, plan),
            buttons=create_time_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("volume_plan_btn_icon:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_data(event.sender_id, "volume_plan_icon_panel_code", str(panel_code))
        await set_data(event.sender_id, "volume_plan_icon_plan_id", str(plan_id))
        await set_step(event.sender_id, "volume_plan_set_icon")
        await event.edit(
            "📎 آیدی سند ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_volume_plan_display:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("time_plan_btn_icon:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        await set_data(event.sender_id, "time_plan_icon_panel_code", str(panel_code))
        await set_data(event.sender_id, "time_plan_icon_plan_id", str(plan_id))
        await set_step(event.sender_id, "time_plan_set_icon")
        await event.edit(
            "📎 آیدی سند ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_time_plan_display:{panel_code}:{plan_id}")]],
        )

    elif data.startswith("volume_plan_btn_icon_clear:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _clear_icon(settings):
            update_volume_plan_in_feature_settings(settings, plan_id, clear_button_icon=True)

        if not await mutate_panel_feature_settings(panel_code, _clear_icon):
            await event.answer("❌ خطا در ذخیره.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer("آیکون دکمه حذف شد.")
        await event.edit(
            volume_plan_display_config_text(panel, plan),
            buttons=create_volume_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("time_plan_btn_icon_clear:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _clear_icon(settings):
            update_time_plan_in_feature_settings(settings, plan_id, clear_button_icon=True)

        if not await mutate_panel_feature_settings(panel_code, _clear_icon):
            await event.answer("❌ خطا در ذخیره.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer("آیکون دکمه حذف شد.")
        await event.edit(
            time_plan_display_config_text(panel, plan),
            buttons=create_time_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("volume_plan_btn_display_reset:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _reset(settings):
            update_volume_plan_in_feature_settings(settings, plan_id, reset_display=True)

        if not await mutate_panel_feature_settings(panel_code, _reset):
            await event.answer("❌ خطا در ریست.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer("تنظیمات نمایش ریست شد.")
        await event.edit(
            volume_plan_display_config_text(panel, plan),
            buttons=create_volume_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("time_plan_btn_display_reset:"):
        parts = data.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])

        def _reset(settings):
            update_time_plan_in_feature_settings(settings, plan_id, reset_display=True)

        if not await mutate_panel_feature_settings(panel_code, _reset):
            await event.answer("❌ خطا در ریست.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id)
        if not panel or not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return
        await event.answer("تنظیمات نمایش ریست شد.")
        await event.edit(
            time_plan_display_config_text(panel, plan),
            buttons=create_time_plan_display_config_submenu(panel_code, plan_id),
        )

    elif data.startswith("panel_webhook_notifications:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            current_status = panel_webhook_notifications_enabled(panel)
            new_status = not current_status
            await panel_manager.update_panel(panel_code, webhook_notifications_enabled=new_status)
            panel = await panel_manager.get_panel_by_code(panel_code)

            status_text = "وب‌هوک 🔔" if new_status else "ربات 🔄"
            await event.answer(f"✅ وضعیت اطلاع‌رسانی به {status_text} تغییر یافت!", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_renew_volume_mode:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            current_status = panel_renew_volume_remaining_mode(panel)
            new_status = not current_status
            await panel_manager.update_panel(panel_code, renew_volume_remaining_mode=new_status)
            panel = await panel_manager.get_panel_by_code(panel_code)

            status_text = "باقیمانده + ریست مصرف (مناسب وب\u200cهوک)" if new_status else "جمع حجم کل (پیش\u200cفرض)"
            await event.answer(f"✅ حالت تمدید حجم: {status_text}", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_settings_help:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        help_text = build_panel_settings_help_text(panel, page)
        help_buttons = build_panel_settings_help_buttons(panel_code, page)
        await event.edit(help_text, buttons=help_buttons, parse_mode="md", link_preview=False)
        await event.answer()

    elif data.startswith("panel_display_mode:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            current_mode = panel_display_mode(panel)
            new_mode = "duration_first" if current_mode == "classic" else "classic"
            await panel_manager.update_panel(panel_code, display_mode=new_mode)
            panel = await panel_manager.get_panel_by_code(panel_code)

            mode_text = "⏰ زمان اول" if new_mode == "duration_first" else "📋 کلاسیک"
            await event.answer(f"✅ نوع نمایش به {mode_text} تغییر کرد", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_subscription_link_mode:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if panel:
            current_mode = resolve_subscription_link_mode(panel)
            next_mode = {
                "both": "main",
                "main": "tunnel",
                "tunnel": "both",
            }[current_mode]
            await panel_manager.update_panel(panel_code, subscription_link_mode=next_mode)
            panel.subscription_link_mode = next_mode

            mode_text = {
                "both": "اصلی + تانل",
                "main": "فقط اصلی",
                "tunnel": "فقط تانل",
            }[next_mode]
            await event.answer(f"✅ نمایش لینک سرویس به {mode_text} تغییر کرد", alert=True)

            info_string = (
                f"<b>┄┄مشخصات پنل┄┄</b>\n"
                f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
                f"🧷 <b>کدپنل:</b> {panel.code}\n"
                f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
                f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
                f"🔄 <b>لینک تانل:</b> {panel.tunnel_url or 'تنظیم نشده'}\n"
            )
            server_status = "وضعیت سرور در حال بررسی است..."
            await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_single_config_links:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        current_selection = panel_single_config_link_indexes(panel)
        current_status = summarize_single_config_link_selection(current_selection)
        buttons = [
            [Button.inline("✏️ تنظیم ایندکس لینک‌ها", data=f"panel_single_config_links_set:{panel_code}")],
        ]
        if current_selection.strip():
            buttons.append(
                [Button.inline("🧹 غیرفعال کردن نمایش لینک تکی", data=f"panel_single_config_links_clear:{panel_code}")]
            )
        buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")])

        await event.edit(
            f"**🔗 تنظیم لینک‌های تکی پنل {panel.name}**\n\n"
            f"📌 مقدار فعلی: `{current_status}`\n\n"
            "ایندکس‌ها از 1 شروع می‌شوند و ترتیب همان خروجی پنل است.\n"
            "مثال‌ها:\n"
            "`1,2,3` برای لینک اول تا سوم\n"
            "`1-3` برای بازه اول تا سوم\n"
            "`all` برای نمایش همه لینک‌ها\n\n"
            "بعد از ذخیره، از placeholderهای زیر داخل متن خرید سرویس و دریافت تست استفاده کن:\n"
            "`{config_links}` یا `{config_links_with_txt}`",
            buttons=buttons,
        )

    elif data.startswith("panel_single_config_links_set:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        await set_data(event.sender_id, "single_config_links_panel_code", str(panel_code))
        await set_step(event.sender_id, "waiting_single_config_links")
        await event.edit(
            "🔗 **تنظیم لینک‌های تکی**\n\n"
            "ایندکس لینک‌هایی که می‌خواهی داخل پیام نمایش داده شوند را وارد کن.\n\n"
            "مثال: `1,2,3` یا `1-3` یا `all`\n"
            "برای غیرفعال کردن می‌توانی `0` هم ارسال کنی.",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_single_config_links:{panel_code}")]],
        )

    elif data.startswith("panel_single_config_links_clear:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        await panel_manager.update_panel(panel_code, single_config_link_indexes="")
        await event.answer("✅ نمایش لینک‌های تکی غیرفعال شد.", alert=True)
        panel.subscription_settings = {
            **subscription_settings(panel),
            "single_config_link_indexes": "",
        }
        info_string = build_panel_summary_block(panel)
        server_status = "وضعیت سرور در حال بررسی است..."
        await update_panel_buttons(event, panel, info_string, server_status)

    elif data.startswith("panel_node_prefixes:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        current_prefixes = panel_node_prefixes(panel)

        default_prefixes = ["LT -", "HYB -", "UL -"]
        all_prefixes = list(set(default_prefixes + current_prefixes))

        buttons = []
        for prefix in all_prefixes:
            is_selected = prefix in current_prefixes
            prefix_display = f"{'✅' if is_selected else '☐'} {prefix}"
            buttons.append([Button.inline(prefix_display, data=f"panel_node_prefix_toggle:{panel_code}:{prefix}")])

        buttons.append([Button.inline("➕ افزودن پیشوند سفارشی", data=f"panel_node_prefix_add_custom:{panel_code}")])

        show_prefixes = panel_show_prefixes_in_locations(panel)
        show_prefixes_status = "✅ نمایش پیشوندها" if show_prefixes else "❌ مخفی کردن پیشوندها"
        buttons.append([Button.inline(show_prefixes_status, data=f"panel_toggle_show_prefixes:{panel_code}")])

        buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")])

        prefix_list = ", ".join(current_prefixes) if current_prefixes else "هیچ پیشوندی انتخاب نشده"
        show_prefixes_text = "✅ فعال" if show_prefixes else "❌ غیرفعال"
        message = (
            f"**🌐 مدیریت پیشوندهای نود - پنل {panel.name}**\n\n"
            f"**پیشوندهای انتخاب شده:**\n`{prefix_list}`\n\n"
            f"**نمایش پیشوندها در لوکیشن‌ها:** {show_prefixes_text}\n\n"
            f"**راهنما:**\n"
            f"• **LT -** برای نودهای حجمی\n"
            f"• **HYB -** برای نودهای ترکیبی (حجمی + نامحدود)\n"
            f"• **UL -** برای نودهای نامحدود\n\n"
            f"برای انتخاب/لغو انتخاب هر پیشوند روی آن کلیک کنید."
        )

        await event.edit(message, buttons=buttons)

    elif data.startswith("panel_node_prefix_toggle:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        prefix = ":".join(parts[2:])

        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        current_prefixes = panel_node_prefixes(panel)

        if prefix in current_prefixes:
            current_prefixes.remove(prefix)
        else:
            current_prefixes.append(prefix)

        new_prefixes_str = ",".join(current_prefixes)
        await panel_manager.update_panel(panel_code, node_prefixes=new_prefixes_str)

        default_prefixes = ["LT -", "HYB -", "UL -"]
        all_prefixes = list(set(default_prefixes + current_prefixes))

        buttons = []
        for p in all_prefixes:
            is_selected = p in current_prefixes
            prefix_display = f"{'✅' if is_selected else '☐'} {p}"
            buttons.append([Button.inline(prefix_display, data=f"panel_node_prefix_toggle:{panel_code}:{p}")])

        buttons.append([Button.inline("➕ افزودن پیشوند سفارشی", data=f"panel_node_prefix_add_custom:{panel_code}")])

        show_prefixes = panel_show_prefixes_in_locations(panel)
        show_prefixes_status = "✅ نمایش پیشوندها" if show_prefixes else "❌ مخفی کردن پیشوندها"
        buttons.append([Button.inline(show_prefixes_status, data=f"panel_toggle_show_prefixes:{panel_code}")])

        buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")])

        prefix_list = ", ".join(current_prefixes) if current_prefixes else "هیچ پیشوندی انتخاب نشده"
        show_prefixes_text = "✅ فعال" if show_prefixes else "❌ غیرفعال"
        message = (
            f"**🌐 مدیریت پیشوندهای نود - پنل {panel.name}**\n\n"
            f"**پیشوندهای انتخاب شده:**\n`{prefix_list}`\n\n"
            f"**نمایش پیشوندها در لوکیشن‌ها:** {show_prefixes_text}\n\n"
            f"**راهنما:**\n"
            f"• **LT -** برای نودهای حجمی\n"
            f"• **HYB -** برای نودهای ترکیبی (حجمی + نامحدود)\n"
            f"• **UL -** برای نودهای نامحدود\n\n"
            f"برای انتخاب/لغو انتخاب هر پیشوند روی آن کلیک کنید."
        )

        await event.edit(message, buttons=buttons)
        await event.answer("✅ پیشوند به‌روزرسانی شد!", alert=False)

    elif data.startswith("panel_node_prefix_add_custom:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        await set_data(event.sender_id, "panel_node_prefix_panel_code", panel_code)
        await set_step(event.sender_id, "waiting_custom_node_prefix")

        await event.edit(
            "**➕ افزودن پیشوند سفارشی**\n\n"
            "لطفاً پیشوند مورد نظر خود را وارد کنید:\n\n"
            "**مثال:** `TUN -`\n\n"
            "⚠️ توجه: پیشوند را دقیقاً همان‌طور که در نام نودها استفاده می‌کنید وارد کنید (با فاصله و کاراکترهای خاص).",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_node_prefixes:{panel_code}")]],
        )

    elif data.startswith("panel_toggle_show_prefixes:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        current_status = panel_show_prefixes_in_locations(panel)
        new_status = not current_status
        await panel_manager.update_panel(panel_code, show_prefixes_in_locations=new_status)
        panel.show_prefixes_in_locations = new_status

        status_text = "فعال ✅" if new_status else "غیرفعال ❌"
        await event.answer(f"✅ نمایش پیشوندها به {status_text} تغییر یافت!", alert=True)

        current_prefixes = panel_node_prefixes(panel)

        default_prefixes = ["LT -", "HYB -", "UL -"]
        all_prefixes = list(set(default_prefixes + current_prefixes))

        buttons = []
        for prefix in all_prefixes:
            is_selected = prefix in current_prefixes
            prefix_display = f"{'✅' if is_selected else '☐'} {prefix}"
            buttons.append([Button.inline(prefix_display, data=f"panel_node_prefix_toggle:{panel_code}:{prefix}")])

        buttons.append([Button.inline("➕ افزودن پیشوند سفارشی", data=f"panel_node_prefix_add_custom:{panel_code}")])

        show_prefixes_status = "✅ نمایش پیشوندها" if new_status else "❌ مخفی کردن پیشوندها"
        buttons.append([Button.inline(show_prefixes_status, data=f"panel_toggle_show_prefixes:{panel_code}")])

        buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")])

        prefix_list = ", ".join(current_prefixes) if current_prefixes else "هیچ پیشوندی انتخاب نشده"
        message = (
            f"**🌐 مدیریت پیشوندهای نود - پنل {panel.name}**\n\n"
            f"**پیشوندهای انتخاب شده:**\n`{prefix_list}`\n\n"
            f"**نمایش پیشوندها در لوکیشن‌ها:** {status_text}\n\n"
            f"**راهنما:**\n"
            f"• **LT -** برای نودهای حجمی\n"
            f"• **HYB -** برای نودهای ترکیبی (حجمی + نامحدود)\n"
            f"• **UL -** برای نودهای نامحدود\n\n"
            f"برای انتخاب/لغو انتخاب هر پیشوند روی آن کلیک کنید."
        )

        await event.edit(message, buttons=buttons)

    elif data.startswith("panel_delete_confirm:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        panel_name = panel.name
        deleted = await PanelsManager().delete_panel(code=panel_code)
        if deleted:
            setting = await SettingsManager().get_settings()
            if setting.test_panel_id == panel_code:
                await SettingsManager().update_setting(setting.id, test_panel_id=0)
            await event.answer(f"✅ پنل «{panel_name}» حذف شد.", alert=True)
            await set_step(event.sender_id, "Menu_panels")
            await display_panels(event.sender_id, current_page=1, edit_message=True, original_event=event)
        else:
            await event.answer("❌ خطا در حذف پنل!", alert=True)

    elif data.startswith("panel_delete:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await event.edit(
            f"⚠️ <b>تایید حذف پنل</b>\n\n"
            f"🏷️ <b>اسم:</b> {panel.name}\n"
            f"🧷 <b>کد:</b> <code>{panel.code}</code>\n\n"
            f"⚠️ این عملیات غیرقابل بازگشت است!\n"
            f"تمام تنظیمات این پنل از دیتابیس حذف می‌شود.",
            parse_mode="html",
            buttons=[
                [Button.inline("✅ بله، حذف کن", data=f"panel_delete_confirm:{panel_code}")],
                [Button.inline("❌ انصراف", data=f"panel_info:{panel_code}")],
            ],
        )

    elif data.startswith("panel_set_test_server:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        setting = await SettingsManager().get_settings()
        await SettingsManager().update_setting(setting.id, test_panel_id=panel_code)
        await event.answer(f"✅ پنل «{panel.name}» به عنوان سرور تست تنظیم شد.", alert=True)
        panel = await PanelsManager().get_panel_by_code(panel_code)
        text, buttons = await build_panel_test_settings_content(panel)
        await event.edit(text, parse_mode="html", buttons=buttons)

    elif data.startswith("panel_disable_test_server:"):
        panel_code = int(data.split(":")[1])
        setting = await SettingsManager().get_settings()
        if setting.test_panel_id != panel_code:
            await event.answer("این پنل سرور تست فعال نیست.", alert=True)
            return
        await SettingsManager().update_setting(setting.id, test_panel_id=0)
        await event.answer("✅ سرور تست غیرفعال شد.", alert=True)
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if panel:
            text, buttons = await build_panel_test_settings_content(panel)
            await event.edit(text, parse_mode="html", buttons=buttons)

    elif data.startswith("panel_test_settings:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)

        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        text, buttons = await build_panel_test_settings_content(panel)
        await event.edit(text, parse_mode="html", buttons=buttons)

    elif data.startswith("panel_test_volume:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await set_data(event.sender_id, "test_volume", str(panel_code))
        await set_step(event.sender_id, "test_volume")
        await event.edit(
            "📥 لطفاً حجم تست را به گیگابایت وارد کنید:\n\nمثال: 2 یا 0.5 یا 10",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_test_settings:{panel_code}")]],
        )

    elif data.startswith("panel_test_duration:"):
        panel_code = int(data.split(":")[1])
        panel = await PanelsManager().get_panel_by_code(panel_code)
        if not panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return
        await set_data(event.sender_id, "test_duration", str(panel_code))
        await set_step(event.sender_id, "test_duration")
        await event.edit(
            "⏰ لطفاً مدت زمان تست را به روز وارد کنید:\n\nمثال: 3 یا 7 یا 30",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_test_settings:{panel_code}")]],
        )

    elif data.startswith("clear_panel_tunnel_url:"):
        panel_code = int(data.split(":")[1])
        panel_manager = PanelsManager()
        await panel_manager.update_panel(panel_code, tunnel_url=None)

        panel = await panel_manager.get_panel_by_code(panel_code)
        await event.answer("✅ لینک تانل حذف شد!", alert=True)

        # Refresh panel info
        info_string = build_panel_summary_block(panel)

        try:
            if not panel.cookie:
                raise ValueError("کوکی نامعتبر است یا وجود ندارد.")

            api = create_panel_api(panel)
            system_stats = await api.get_system_stats(admin_username=panel.username)

            server_status = (
                "┄┄<b>وضعیت سرور</b>┄┄\n"
                f"🔖 <b>نسخه:</b> {system_stats.version}\n"
                f"🧠 <b>مجموع رم:</b> {round(system_stats.mem_total / (1024**3), 2)} گیگ\n"
                f"📊 <b>رم استفاده‌شده:</b> {round(system_stats.mem_used / (1024**3), 2)} گیگ\n"
                f"🧩 <b>تعداد هسته سی‌پی‌یو:</b> {system_stats.cpu_cores}\n"
                f"📉 <b>درصد استفاده سی‌پی‌یو:</b> {system_stats.cpu_usage}%\n"
                f"👤 <b>تعداد کل کاربران:</b> {system_stats.total_user}\n"
                f"🟢 <b>کاربران آنلاین:</b> {system_stats.online_users}\n"
                f"✅ <b>کاربران فعال:</b> {system_stats.active_users}\n"
                f"⏸️ <b>کاربران آن‌هولد:</b> {system_stats.on_hold_users}\n"
                f"🚫 <b>کاربران غیرفعال:</b> {system_stats.disabled_users}\n"
                f"📆 <b>کاربران تاریخ‌گذشته:</b> {system_stats.expired_users}\n"
                f"📉 <b>کاربران دارای محدودیت:</b> {system_stats.limited_users}\n"
                f"📥 <b>دانلود کل:</b> {round(system_stats.incoming_bandwidth / (1024**3), 2)} گیگ\n"
                f"📤 <b>آپلود کل:</b> {round(system_stats.outgoing_bandwidth / (1024**3), 2)} گیگ\n"
            )
        except Exception as e:
            error_message = str(e)
            if "401 Unauthorized" in error_message and not panel_uses_api_key(panel):
                try:
                    await refresh_panel_cookie(panel)
                    server_status = "┄┄<b>وضعیت سرور</b>┄┄\n✅ کوکی جدید دریافت شد."
                except Exception as e2:
                    server_status = f"خطا در بازیابی کوکی جدید: {e2!s}"
            else:
                server_status = f"خطا در دریافت وضعیت سرور: {error_message}"

        await update_panel_buttons(event, panel, info_string, server_status)

    elif data == "backPanel_list":
        # update_user(event.sender_id, 'Menu_panels')
        if event.sender_id in ADMIN_ID:
            # await event.delete()
            user_id = event.sender_id
            await set_step(user_id=user_id, step="Menu_panels")
            await display_panels(user_id, current_page=1, edit_message=True, original_event=event)

    elif data.startswith("set_panel_login_path:"):
        panel_id = int(data.split(":")[1])
        await event.edit(
            "🔗 **مسیر ورود ادمین (برای نمایندگان)**\n\n"
            "اگر API روی `https://domain.com` است ولی ورود ادمین روی `https://domain.com/admin` است،\n"
            "فقط `admin` را ارسال کنید.\n"
            "برای پاک کردن، `-` بفرستید.",
            buttons=[Button.inline("❌ انصراف", data=f"panel_info:{panel_id}")],
            parse_mode="markdown",
        )
        await set_step(event.sender_id, "SetPanelLoginPath")
        await set_data(event.sender_id, "SetPanelLoginPath", panel_id)

    elif data.startswith("set_panel_tunnel_url:"):
        parts = data.split(":")
        panel_id = int(parts[1])
        await event.edit(
            "🌐 لطفاً دامنه یا IP تانل شده را وارد کنید:\n\nمثال: https://tunnel.example.com",
            buttons=[Button.inline("❌ انصراف", data=f"panel_info:{panel_id}")],
        )
        await set_step(event.sender_id, "SetPanelTunnelUrl")
        await set_data(event.sender_id, "SetPanelTunnelUrl", panel_id)

    elif data.startswith("change_panel_name:"):
        parts = data.split(":")
        panel_id = int(parts[1])
        await event.edit(
            "📝 لطفاً نام پنل جدید را وارد کنید:",
            buttons=[Button.inline("بازگشت", data=f"panel_info:{panel_id}")],
        )
        await set_step(event.sender_id, "ChangePanelName")
        await set_data(event.sender_id, "ChangePanelName", panel_id)

    elif data.startswith("PrevDiscount:") or data.startswith("NextDiscount:"):
        current_page = int(data.split(":")[1])

        discount_codes = await DiscountCodeManager().get_all_discount_codes()
        total_codes = len(discount_codes)
        per_page = 6
        num_pages = (total_codes + per_page - 1) // per_page

        if data.startswith("PrevDiscount:"):
            if current_page > 1:
                current_page -= 1
        elif data.startswith("NextDiscount:") and current_page < num_pages:
            current_page += 1

        current_page = max(1, min(current_page, num_pages))

        await UserCRUD().update_user(user_id=event.sender_id, page=current_page)

        try:
            await show_discount_codes(
                admin_id=event.sender_id, page=current_page, per_page=per_page, edit=True, origin_event=event
            )
        except Exception as e:
            logger.error(f"Error in discount codes pagination: {e}")

            if "MessageNotModifiedError" in str(e):
                await show_discount_codes(
                    admin_id=event.sender_id,
                    page=current_page,
                    per_page=per_page,
                    edit=False,
                    origin_event=None,
                )

    elif data.startswith("prev:") or data.startswith("next:"):
        current_page = int(data.split(":")[1])
        panels = await PanelsManager().get_all_panels()
        total_panels = len(panels)
        PANEL_LIMIT = 10

        num_pages = (total_panels + PANEL_LIMIT - 1) // PANEL_LIMIT

        if data.startswith("prev:"):
            if current_page > 1:
                current_page -= 1
        elif data.startswith("next:") and current_page < num_pages:
            current_page += 1

        current_page = max(1, min(current_page, num_pages))

        await display_panels(event.sender_id, current_page, edit_message=True, original_event=event)
    return


def register(client):
    client.add_event_handler(panel_admin_callback_handler, events.CallbackQuery(func=panel_admin_callback_filter))

"""Shared helpers for admin panel management flow."""

from __future__ import annotations

import contextlib

from telethon import Button
from telethon.errors.rpcerrorlist import MessageNotModifiedError

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.panels.auth import panel_auth_type_label
from app.services.panels.settings import (
    panel_reseller_sale_flag,
    panel_shop_sale_flag,
    panel_test_duration_days,
    panel_test_volume_gb,
)
from app.telegram.shared.keyboards.panel_buttons import (
    build_panel_admin_settings_buttons,
    build_panel_list_rows,
    build_panel_ms_buttons_menu,
    panel_ms_buttons_menu_text,
)
from app.utils.formatting.conversions import convert_storage

logger = get_logger(__name__)


def build_panel_summary_block(panel) -> str:
    return (
        f"<b>┄┄مشخصات پنل┄┄</b>\n"
        f"🏷️ <b>اسم پنل:</b> {panel.name}\n"
        f"🧷 <b>کدپنل:</b> {panel.code}\n"
        f"📶 <b>وضعیت:</b> {'فعال ✅' if panel.enable else 'غیرفعال ❌'}\n"
        f"🛒 <b>فروش سرویس:</b> {'فعال ✅' if panel_shop_sale_flag(panel) else 'غیرفعال ❌'}\n"
        f"🏢 <b>فروش نمایندگی:</b> {'فعال ✅' if panel_reseller_sale_flag(panel) else 'غیرفعال ❌'}\n"
        f"🌐 <b>آدرس پنل:</b> {panel.base_url}\n"
        f"🔄 <b>لینک تانل:</b> {panel.tunnel_url or 'تنظیم نشده'}\n"
        f"🔐 <b>نوع ورود:</b> {panel_auth_type_label(panel)}"
    )


async def update_panel_buttons(event, panel, info_string, server_status):
    try:
        buttons = build_panel_admin_settings_buttons(panel)

        await event.edit(
            f'<blockquote expandable>{info_string}</blockquote>\n<blockquote expandable>{server_status}</blockquote>\nCoded By <a href="https://github.com/AmirKenzo">AmirKenzoo</a>',
            parse_mode="html",
            link_preview=False,
            buttons=buttons,
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await event.answer("❌ خطا در بروزرسانی وضعیت.")


async def show_panel_ms_buttons_menu(event, panel) -> None:
    with contextlib.suppress(MessageNotModifiedError):
        await event.edit(
            panel_ms_buttons_menu_text(panel),
            buttons=build_panel_ms_buttons_menu(panel),
            parse_mode="md",
            link_preview=False,
        )


async def build_panel_test_settings_content(panel) -> tuple[str, list]:
    setting = await SettingsManager().get_settings()
    is_test_panel = setting.test_panel_id == panel.code
    test_volume = panel_test_volume_gb(panel)
    test_duration = panel_test_duration_days(panel)
    test_volume_text = convert_storage(test_volume, for_button=True)

    if is_test_panel:
        test_server_line = "🆓 <b>سرور تست:</b> ✅ این پنل فعال است"
    elif setting.test_panel_id:
        test_server_line = f"🆓 <b>سرور تست:</b> پنل دیگر (کد `{setting.test_panel_id}`)"
    else:
        test_server_line = "🆓 <b>سرور تست:</b> غیرفعال"

    text = (
        f"<b>🧪 تنظیمات کانفیگ تست</b>\n\n"
        f"📥 <b>حجم فعلی:</b> {test_volume_text}\n"
        f"⏰ <b>زمان فعلی:</b> {test_duration} روز\n"
        f"{test_server_line}\n\n"
        f"برای تغییر هر کدام روی دکمه مربوطه کلیک کنید."
    )

    panel_code = panel.code
    buttons = [
        [Button.inline(f"📥 حجم تست: {test_volume_text}", data=f"panel_test_volume:{panel_code}")],
        [Button.inline(f"⏰ زمان تست: {test_duration} روز", data=f"panel_test_duration:{panel_code}")],
    ]
    if is_test_panel:
        buttons.append([Button.inline("❌ غیرفعال کردن سرور تست", data=f"panel_disable_test_server:{panel_code}")])
    else:
        buttons.append([Button.inline("🆓 تنظیم به عنوان سرور تست", data=f"panel_set_test_server:{panel_code}")])
    buttons.append([Button.inline("🔙 برگشت", data=f"panel_info:{panel_code}")])
    return text, buttons


async def display_panels(user_id, current_page, edit_message=False, original_event=None):
    manager = PanelsManager()
    panels = await manager.get_all_panels_reverse()
    panel_limit = 10

    if not panels:
        await Kenzo.send_message(entity=user_id, message="هیچ پنلی موجود نیست.")
        return

    total_panels = len(panels)
    num_pages = (total_panels + panel_limit - 1) // panel_limit
    start_index = (current_page - 1) * panel_limit
    end_index = start_index + panel_limit

    current_panels = panels[start_index:end_index]
    panel_buttons = await build_panel_list_rows(current_panels)

    navigation_buttons = []
    if current_page > 1:
        navigation_buttons.append(Button.inline("صفحه قبلی ->", data=f"prev:{current_page}"))
    if current_page < num_pages:
        navigation_buttons.append(Button.inline("<- صفحه بعدی", data=f"next:{current_page}"))

    footer_buttons = []
    if navigation_buttons:
        footer_buttons.append(navigation_buttons)
    all_buttons = panel_buttons + footer_buttons

    if edit_message and original_event:
        await Kenzo.edit_message(
            entity=original_event.original_update.user_id,
            message=original_event.original_update.msg_id,
            text=f"**📉 وضعیت پنل ها**\n**تعداد پنل ها:** `{total_panels}`",
            buttons=all_buttons,
        )
    else:
        await Kenzo.send_message(
            entity=user_id,
            message=f"**📉 وضعیت پنل ها**\n**تعداد پنل ها:** `{total_panels}`",
            buttons=all_buttons,
        )


def _is_number(msg: str) -> bool:
    try:
        float(msg)
        return True
    except ValueError:
        return False


async def mutate_panel_feature_settings(panel_code: int, mutator) -> bool:
    panel_manager = PanelsManager()
    panel = await panel_manager.get_panel_by_code(panel_code)
    if not panel:
        return False
    from app.services.panels.settings import compact_feature_settings, feature_settings

    settings = feature_settings(panel)
    mutator(settings)
    settings = compact_feature_settings(settings)
    return await panel_manager.update_panel(panel_code, feature_settings=settings)


async def show_panel_volume_plans_menu(event, panel) -> None:
    from app.telegram.shared.keyboards.panel_buttons import (
        build_panel_volume_plans_admin_buttons,
        panel_volume_plans_admin_text,
    )

    await event.edit(
        panel_volume_plans_admin_text(panel),
        buttons=build_panel_volume_plans_admin_buttons(panel),
    )


async def show_panel_time_plans_menu(event, panel) -> None:
    from app.telegram.shared.keyboards.panel_buttons import (
        build_panel_time_plans_admin_buttons,
        panel_time_plans_admin_text,
    )

    await event.edit(
        panel_time_plans_admin_text(panel),
        buttons=build_panel_time_plans_admin_buttons(panel),
    )

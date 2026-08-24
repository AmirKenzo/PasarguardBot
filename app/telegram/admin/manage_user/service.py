"""Shared helpers for admin manage_user."""

import asyncio
import random

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI, UserCreate
from pasarguard.enums import UserDataLimitResetStrategy
from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.services.panels.auth import fetch_panel_groups_with_auth
from app.services.panels.groups import resolve_panel_group_ids
from app.telegram.admin.manage_user import states
from app.telegram.keyboards.common import styled_copy_button, styled_webview_button
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.state import clear_user, get_data, set_step
from app.utils.formatting.conversions import day_to_timestamp, gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size
from app.utils.media.qrcode import create_qr_code

logger = get_logger(__name__)

ADMIN_SERVICE_LIST_PREFIX = states.ADMIN_SERVICE_LIST_PREFIX


async def delete_message(event, offset=0, delay=0):
    try:
        target_message_id = event.message.id + offset
        if delay > 0:
            await asyncio.sleep(delay)
        await event.client.delete_messages(event.chat_id, target_message_id)
    except Exception:
        pass


async def finalize_admin_config(event, username: str):
    panel_code = await get_data(event.sender_id, "AdminPanel")
    gbConfig = await get_data(event.sender_id, "GBConfig")
    timeConfig = await get_data(event.sender_id, "TimeConfig")
    user_id = await get_data(event.sender_id, "UserID")

    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    try:
        await PasarguardAPI(panel.base_url).get_user_by_username(username=username, token=panel.cookie)
        await event.respond(
            "❌ این نام کانفیگ در پنل قبلاً توسط شخص دیگری ساخته شده است.\nلطفاً نام دیگری وارد کنید:",
            buttons=[Button.inline("✨ یه اسم رندوم بده", b"admin_random_username")],
        )
        return
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            await event.respond("خطا در ارتباط با پنل، لطفاً دوباره تلاش کنید.")
            return

    CodeService = random.randint(10000, 9999999)
    groups_resp = await fetch_panel_groups_with_auth(panel)
    group_ids: list[int] = resolve_panel_group_ids(panel, groups_resp)
    new_user = UserCreate(
        username=username,
        group_ids=group_ids,
        data_limit=gigabytes_to_bytes(float(gbConfig)),
        expire=day_to_timestamp(int(timeConfig)),
        note=f"{user_id}",
        data_limit_reset_strategy=UserDataLimitResetStrategy.NO_RESET,
    )
    try:
        added_user = await PasarguardAPI(panel.base_url).add_user(user=new_user, token=panel.cookie)
    except HTTPStatusError as e:
        if e.response.status_code in (409, 400, 422):
            await event.respond(
                "❌ این نام کانفیگ در پنل قبلاً وجود دارد.\nلطفاً نام دیگری وارد کنید:",
                buttons=[Button.inline("✨ یه اسم رندوم بده", b"admin_random_username")],
            )
            return
        raise
    subscription_url = added_user.subscription_url
    subscription_url = (
        subscription_url if subscription_url.startswith("http") else f"{panel.base_url}{subscription_url}"
    )
    qr_file = create_qr_code(text=f"{subscription_url}", filename=f"{CodeService}.png")

    txt = (
        f"**🎉 کانفیگ اختصاصی شما توسط ادمین ساخته شد**\n"
        f"🌐 نام پنل `{panel.name}`\n"
        f"**#️⃣ کد سرویس(در ربات):** `{CodeService}`\n"
        f"**🔷 اسم کانفیگ:** `{username}`\n"
        f"⏳ زمان کانفیگ: {timeConfig} روز\n"
        f"📦 حجم کانفیگ: {gbConfig} گیگ\n"
        f"**🔗 لینک اختصاصی شما:**\n\n"
        f"`{subscription_url}`\n\n"
    )

    log_text = (
        f"📢 ** کانفیگ ساخته شده توسط ادمین**\n\n"
        f"👤 شناسه کاربر: `{user_id}`\n"
        f"📅 تاریخ (میلادی): `{Time_Date()['mf']}`\n"
        f"📅 تاریخ (شمسی): `{Time_Date()['jf']}`\n"
        f"🎫 کد سرویس: `{CodeService}`\n"
        f"**🔷 اسم کانفیگ:** `{username}`\n"
        f"⏳ زمان کانفیگ: {timeConfig} روز\n"
        f"📦 حجم کانفیگ: {gbConfig} گیگ\n"
        f"🎫 کد پنل: `{panel.code}`\n"
        f"🌐 نام پنل `{panel.name}`\n"
        f"🔗 لینک کانفیگ: `{subscription_url}`"
    )

    await Kenzo.send_message(
        int(user_id),
        message=txt,
        file=qr_file,
        buttons=ReplyInlineMarkup(
            [
                KeyboardInlineButtonRow(
                    [
                        styled_webview_button(
                            "برای مشاهده اطلاعات بیشتر کلیک کنید",
                            f"{subscription_url}",
                        )
                    ]
                ),
                KeyboardInlineButtonRow([styled_copy_button("برای کپی لینک کلیک کنید", f"{subscription_url}")]),
            ]
        ),
    )

    await ServiceCRUD().create_service(
        code=CodeService,
        username=username,
        enable=1,
        in_panel=panel.code,
        panel_userid=getattr(added_user, "id", None),
        id=user_id,
        package_size=gigabytes_to_bytes(float(gbConfig)),
        createtime=Time_Date()["stamp"],
        expiration_time=day_to_timestamp(int(timeConfig)),
        is_test=False,
    )
    await send_log_message(LogType.OTHER, message=log_text)
    await event.respond(
        "🍀 کانفیگ برای کاربر ساخته و ارسال شد",
        buttons=[Button.inline("بازگشت", f"BackToUserManagement:{user_id}")],
    )
    await clear_user(event.sender_id)
    await set_step(event.sender_id, "panel")


async def build_service_text(service, panel_name: str, user) -> str:
    identifier = service.username if user.show_config_name else service.code
    if user.show_service_word:
        identifier = f"سرویس {identifier}"
    parts = [str(identifier)]
    if user.show_volume:
        if hasattr(service, "data_limit_reset_strategy") and service.data_limit_reset_strategy != "no_reset":
            reset_text_map = {
                "day": "روزانه",
                "week": "هفتگی",
                "month": "ماهانه",
                "year": "سالانه",
            }
            period_text = reset_text_map.get(getattr(service, "data_limit_reset_strategy", None), "نامحدود")
            per_limit_text = format_size(service.package_size, decimal_places=0)
            parts.append(f"{period_text} {per_limit_text}")
        else:
            parts.append(format_size(service.package_size, decimal_places=1))
    if user.show_panel:
        parts.append(panel_name)
    return " - ".join(parts)


def _admin_service_list_page(page: int | None) -> int:
    return max(1, int(page or 1))


async def display_user_services_Admin(event, user_id, current_page, edit_message=False, original_event=None):
    services = await ServiceCRUD().get_services_reverse(user_id)

    target_user = await UserCRUD().read_user(user_id)
    if not target_user:
        await Kenzo.send_message(entity=event.sender_id, message="کاربر یافت نشد.")
        return

    # Use admin's advanced settings for display (same as admin's own config list)
    display_user = await UserCRUD().read_user(event.sender_id)
    if not display_user:
        display_user = target_user

    row_size = display_user.service_buttons_per_row or 1
    row_count = display_user.service_button_rows or 5
    PANEL_LIMIT = min(row_size * row_count, 20)

    if not services:
        await Kenzo.send_message(entity=event.sender_id, message="کاربر هیچ سرویس فعالی ندارد.")
        return

    total_services = len(services)
    num_pages = max(1, (total_services + PANEL_LIMIT - 1) // PANEL_LIMIT)
    current_page = min(_admin_service_list_page(current_page), num_pages)
    start_index = (current_page - 1) * PANEL_LIMIT
    end_index = start_index + PANEL_LIMIT

    current_services = services[start_index:end_index]

    service_buttons = []
    current_row = []
    for service in current_services:
        PanelName = await PanelsManager().get_panel_by_code(code=service.in_panel)
        panel_display_name = "پنل نامشخص" if PanelName is None else PanelName.name

        text = await build_service_text(service, panel_display_name, display_user)
        current_row.append(Button.inline(text, data=f"service_info_admin:{service.code}"))

        if len(current_row) == row_size:
            service_buttons.append(current_row)
            current_row = []
    if current_row:
        service_buttons.append(current_row)

    navigation_buttons = []
    if current_page > 1:
        navigation_buttons.append(Button.inline("صفحه قبلی ->", data=f"PrevServiceAdmin:{current_page}:{user_id}"))
    if current_page < num_pages:
        navigation_buttons.append(Button.inline("<- صفحه بعدی", data=f"NextServiceAdmin:{current_page}:{user_id}"))

    navigation_buttons.append(Button.inline("Back", data=f"BackToUserManagement:{user_id}"))

    if edit_message and original_event:
        await Kenzo.edit_message(
            entity=event.sender_id,
            message=original_event.original_update.msg_id,
            text=f"**📉 سرویس‌های کاربر**\n**تعداد کل سرویس های شما:** {total_services}\n.",
            buttons=[*service_buttons, navigation_buttons],
        )

    else:
        await Kenzo.send_message(
            entity=event.sender_id,
            message=f"**📉 سرویس‌های کاربر**\n**تعداد کل سرویس های شما:** {total_services}\n.",
            buttons=[*service_buttons, navigation_buttons],
        )

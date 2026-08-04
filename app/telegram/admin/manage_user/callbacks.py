"""Callback handlers for admin manage_user."""

import json
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI, UserModify, UserResponse
from telethon import Button, events

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, safe_mode_admin_label, user_safe_mode_value
from app.logger import LogType, get_logger
from app.services.billing.renewal import require_panel_userid
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.panels.admins import get_reseller_admin, get_reseller_admin_user_count, reset_reseller_admin_password
from app.services.reseller.logging import send_reseller_log
from app.services.reseller.usage_cap import set_reseller_usage_cap, usage_cap_menu_text
from app.services.users.admin_profile import display_user_info_admin
from app.telegram.admin.manage_user import states
from app.telegram.admin.manage_user.service import (
    ADMIN_SERVICE_LIST_PREFIX,
    _admin_service_list_page,
    delete_message,
    display_user_services_Admin,
    finalize_admin_config,
)
from app.telegram.keyboards.admin import (
    Home_Back,
    build_admin_reseller_account_buttons,
    build_admin_reseller_chpwd_confirm_buttons,
    build_admin_reseller_delete_confirm_buttons,
    build_admin_reseller_list_buttons,
    build_admin_reseller_usage_cap_buttons,
    create_inline_manageuser,
)
from app.telegram.keyboards.services import create_inline_service_buttons
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.username import generate_unique_username
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from app.telegram.user.reseller.helpers import (
    build_reseller_account_detail_text,
    delete_reseller_account,
    format_plan_button_text,
    pause_reseller_account_by_admin,
    resume_reseller_account_by_admin,
)
from app.telegram.user.services.helpers import build_service_info_message_text, edit_service_view
from app.utils.formatting.dates import Time_Date, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from app.utils.security.crypto import encrypt_data
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID

logger = get_logger(__name__)


async def _admin_get_user_reseller(user_id: int, account_code: int):
    ok, account = await ResellerAccountCRUD().get_account(account_code)
    if not ok or account.telegram_id != user_id:
        return None
    return account


async def _admin_show_reseller_detail(event, user_id: int, account) -> None:
    text = await build_reseller_account_detail_text(account, show_password=False)
    await event.edit(
        text,
        buttons=build_admin_reseller_account_buttons(user_id, account),
        parse_mode="markdown",
    )


async def handle_admin_reseller_callbacks(event: events.CallbackQuery.Event, data: str) -> bool:
    if not data.startswith("AdminReseller_"):
        return False

    parts = data.split(":")
    action = parts[0].replace("AdminReseller_", "")
    user_id = int(parts[1])
    account_code = int(parts[2]) if len(parts) > 2 else None
    plan_id = int(parts[3]) if len(parts) > 3 else None

    if action == "view":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        await _admin_show_reseller_detail(event, user_id, account)
        return True

    if action == "creds":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        text = await build_reseller_account_detail_text(account, show_password=True)
        await event.edit(
            text,
            buttons=build_admin_reseller_account_buttons(user_id, account),
            parse_mode="markdown",
        )
        return True

    if action == "pause":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        ok, msg = await pause_reseller_account_by_admin(account, actor_id=event.sender_id)
        await event.answer(msg, alert=True)
        if ok:
            ok, account = await ResellerAccountCRUD().get_account(account_code)
            if ok:
                await _admin_show_reseller_detail(event, user_id, account)
        return True

    if action == "resume":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        ok, msg = await resume_reseller_account_by_admin(account, actor_id=event.sender_id)
        await event.answer(msg, alert=True)
        if ok:
            ok, account = await ResellerAccountCRUD().get_account(account_code)
            if ok:
                await _admin_show_reseller_detail(event, user_id, account)
        return True

    if data.startswith("AdminReseller_delete:") and not data.startswith("AdminReseller_delete_confirm:"):
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        sub_users = 0
        if panel:
            try:
                sub_users = await get_reseller_admin_user_count(panel, account.username)
            except Exception:
                sub_users = 0
        await event.edit(
            f"**⚠️ حذف نمایندگی `{account.username}`**\n\n"
            f"• ادمین پنل حذف می‌شود\n"
            f"• `{sub_users}` یوزر وابسته حذف می‌شوند\n"
            f"• این عمل غیرقابل بازگشت است",
            buttons=build_admin_reseller_delete_confirm_buttons(user_id, account_code),
            parse_mode="markdown",
        )
        return True

    if data.startswith("AdminReseller_delete_confirm:"):
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        ok, msg = await delete_reseller_account(account, actor_id=event.sender_id, actor_role="ادمین")
        await event.answer(msg, alert=True)
        if ok:
            accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
            if accounts:
                await event.edit(
                    f"**🏢 نمایندگی‌های کاربر `{user_id}`** ({len(accounts)} مورد)\n\nیک نمایندگی را انتخاب کنید:",
                    buttons=build_admin_reseller_list_buttons(user_id, accounts),
                    parse_mode="markdown",
                )
            else:
                await event.edit(
                    f"**🏢 نمایندگی‌های کاربر `{user_id}`**\n\nنمایندگی فعالی ندارد.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"BackToUserManagement:{user_id}")]],
                    parse_mode="markdown",
                )
        return True

    if action == "chpwd":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        await event.edit(
            f"**⚠️ تغییر رمز `{account.username}`**\n\nرمز جدید ساخته می‌شود. ادامه می‌دهید؟",
            buttons=build_admin_reseller_chpwd_confirm_buttons(user_id, account_code),
            parse_mode="markdown",
        )
        return True

    if data.startswith("AdminReseller_chpwd_confirm:"):
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return True
        try:
            new_password = await reset_reseller_admin_password(panel, account.username)
        except Exception as exc:
            logger.error("admin reseller password reset failed: %s", exc)
            await event.answer("خطا در تغییر رمز.", alert=True)
            return True
        await ResellerAccountCRUD().update_account(account.code, password_encrypted=encrypt_data(new_password))
        await send_reseller_log(
            "🔑 تغییر رمز نمایندگی توسط ادمین",
            account=account,
            actor_id=event.sender_id,
            actor_role="ادمین",
        )
        ok, account = await ResellerAccountCRUD().get_account(account_code)
        if ok:
            text = await build_reseller_account_detail_text(account, show_password=True)
            await event.edit(
                text,
                buttons=build_admin_reseller_account_buttons(user_id, account),
                parse_mode="markdown",
            )
        await event.answer("✅ رمز جدید اعمال شد.", alert=False)
        return True

    if data.startswith("AdminReseller_renew_plan:"):
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan or plan.pricing_mode != "fixed":
            await event.answer("پلن نامعتبر است.", alert=True)
            return True
        success, msg = await renew_reseller_account(
            account_code,
            plan_id,
            user_id,
            actor_id=event.sender_id,
            actor_role="ادمین",
        )
        await event.answer(msg, alert=True)
        if success:
            ok, account = await ResellerAccountCRUD().get_account(account_code)
            if ok:
                await _admin_show_reseller_detail(event, user_id, account)
        return True

    if data.startswith("AdminReseller_renew:"):
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        plans = [
            p
            for p in await ResellerPlanManager().get_all_plans(panel_code=account.panel_code, enabled_only=True)
            if p.pricing_mode == "fixed"
        ]
        if not plans:
            await event.answer("پلن ثابت فعالی نیست.", alert=True)
            return True
        rows = [
            [
                Button.inline(
                    format_plan_button_text(plan), data=f"AdminReseller_renew_plan:{user_id}:{account_code}:{plan.id}"
                )
            ]
            for plan in plans
        ]
        rows.append([Button.inline("🔙 بازگشت", data=f"AdminReseller_view:{user_id}:{account_code}")])
        await event.edit(
            f"**💎 تمدید `{account.username}`**\n\nپلن را انتخاب کنید:",
            buttons=rows,
            parse_mode="markdown",
        )
        return True

    if action == "usage_cap":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        if account.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return True
        await delete_data(event.sender_id, "AdminResellerUsageCapUserId")
        await delete_data(event.sender_id, "AdminResellerUsageCapCode")
        await set_step(event.sender_id, "MToUserInfo")
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        used = 0
        if panel:
            try:
                admin = await get_reseller_admin(panel, account.username)
                used = int(getattr(admin, "used_traffic", 0) or 0) if admin else 0
            except Exception:
                used = 0
        await event.edit(
            usage_cap_menu_text(account, used_bytes=used),
            buttons=build_admin_reseller_usage_cap_buttons(
                user_id, account_code, has_cap=bool(account.usage_cap_bytes)
            ),
            parse_mode="markdown",
        )
        return True

    if action == "usage_cap_set":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        if account.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return True
        await set_data(event.sender_id, "AdminResellerUsageCapUserId", str(user_id))
        await set_data(event.sender_id, "AdminResellerUsageCapCode", str(account_code))
        await set_step(event.sender_id, "AdminResellerUsageCapInput")
        await event.edit(
            f"**📦 تنظیم سقف مصرف — `{account.username}`**\n\n"
            "مقدار سقف را به **گیگابایت** ارسال کنید.\n"
            "مثال: `50`\n\n"
            "برای حذف محدودیت عدد `0` بفرستید.",
            buttons=[[Button.inline("🔙 بازگشت", data=f"AdminReseller_usage_cap:{user_id}:{account_code}")]],
            parse_mode="markdown",
        )
        return True

    if action == "usage_cap_clear":
        account = await _admin_get_user_reseller(user_id, account_code)
        if not account:
            await event.answer("نمایندگی یافت نشد.", alert=True)
            return True
        if account.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return True
        ok, msg = await set_reseller_usage_cap(
            account,
            gigabytes=None,
            actor_id=event.sender_id,
            actor_role="ادمین",
        )
        await event.answer(msg, alert=True)
        if ok:
            ok, account = await ResellerAccountCRUD().get_account(account_code)
            if ok:
                await _admin_show_reseller_detail(event, user_id, account)
        return True

    return False


def is_manage_user_service_callback(data: str) -> bool:
    if data == "admin_random_username":
        return True
    return any(data.startswith(prefix) for prefix in states.MANAGE_USER_SERVICE_CALLBACK_PREFIXES)


async def handle_manage_user_service_callbacks(event: events.CallbackQuery.Event, data: str) -> None:
    if data.startswith("DeleteServiceAdmin:"):
        parts = data.split(":")
        if len(parts) < 2:
            await event.answer("Invalid data.", alert=True)
            return
        service_code = int(parts[1])
        _, serv = await ServiceCRUD().get_service(code=service_code)
        if not serv:
            await event.answer("Service not found.", alert=True)
            return
        await event.edit(
            "نحوه حذف را انتخاب کنید:",
            buttons=[
                [
                    Button.inline("فقط از دیتابیس ربات", data=f"DeleteServiceAdmin_confirm:{service_code}:db"),
                    Button.inline("فقط از پنل", data=f"DeleteServiceAdmin_confirm:{service_code}:panel"),
                ],
                [Button.inline("از هر دو", data=f"DeleteServiceAdmin_confirm:{service_code}:both")],
                [Button.inline("بازگشت", data=f"service_info_admin:{service_code}")],
            ],
        )

    elif data.startswith("DeleteServiceAdmin_confirm:"):
        parts = data.split(":")
        if len(parts) != 3:
            await event.answer("Invalid data.", alert=True)
            return
        service_code_str, mode = parts[1], parts[2]
        service_code = int(service_code_str)
        _, Userid = await ServiceCRUD().get_service(code=service_code)
        if not Userid:
            await event.answer("Service not found.", alert=True)
            return
        owner_id = Userid.id
        Panel = await PanelsManager().get_panel_by_code(code=Userid.in_panel)
        log_reason = ""
        try:
            if mode in ("panel", "both") and Panel is not None:
                await PasarguardAPI(base_url=Panel.base_url).remove_user_by_id(
                    user_id=require_panel_userid(Userid), token=Panel.cookie
                )
                log_reason = "panel only" if mode == "panel" else "panel and DB"
            elif mode == "panel" and Panel is None:
                await event.edit(
                    "پنل یافت نشد. حذف از پنل ممکن نیست.",
                    buttons=[Button.inline("بازگشت", data=f"{ADMIN_SERVICE_LIST_PREFIX}:{owner_id}")],
                )
                return
            if mode in ("db", "both"):
                await ServiceCRUD().delete_service(code=service_code)
                log_reason = "DB only" if mode == "db" else "panel and DB"
            msg_map = {
                "db": "فقط از دیتابیس ربات حذف شد.",
                "panel": "فقط از پنل حذف شد.",
                "both": "از پنل و دیتابیس ربات حذف شد.",
            }
            log_text = (
                f"🗑️ **حذف سرویس**\n\n"
                f"📍 شناسه سرویس: `{Userid.id}`\n"
                f"🔷 نام کاربری: `{Userid.username}`\n"
                f"🕒 تاریخ حذف (میلادی): `{Time_Date()['mf']}`\n"
                f"🕒 تاریخ حذف (شمسی): `{Time_Date()['jf']}`\n"
                f"💬 دلیل: {log_reason}"
            )
            await send_log_message(LogType.OTHER, message=log_text)
            await event.edit(
                msg_map.get(mode, "انجام شد."),
                buttons=[Button.inline("بازگشت", data=f"{ADMIN_SERVICE_LIST_PREFIX}:{owner_id}")],
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404 and mode in ("panel", "both"):
                if mode == "both":
                    await ServiceCRUD().delete_service(code=service_code)
                await event.edit(
                    "کاربر در پنل یافت نشد؛ فقط از دیتابیس حذف شد." if mode == "both" else "کاربر در پنل یافت نشد.",
                    buttons=[Button.inline("بازگشت", data=f"{ADMIN_SERVICE_LIST_PREFIX}:{owner_id}")],
                )
                log_text = (
                    f"🗑️ **حذف سرویس**\n\n"
                    f"📍 شناسه سرویس: `{Userid.id}`\n"
                    f"🔷 نام کاربری: `{Userid.username}`\n"
                    f"🕒 تاریخ حذف (میلادی): `{Time_Date()['mf']}`\n"
                    f"🕒 تاریخ حذف (شمسی): `{Time_Date()['jf']}`\n"
                    f"💬 دلیل: user not on panel; DB delete applied."
                )
                await send_log_message(LogType.OTHER, message=log_text)
            else:
                logger.error("HTTP error on delete:", exc_info=True)
                await event.edit("خطا. لطفاً دوباره تلاش کنید.")
        except Exception:
            logger.error("Delete error:", exc_info=True)
            await event.edit("خطا. لطفاً دوباره تلاش کنید.")

    elif data.startswith("service_info_admin:"):
        service_code = data.split(":")[1]
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return

        InfoPanel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if InfoPanel is None:
            await event.edit(
                "پنل یافت نشد! آیا می‌خواهید سرویس را حذف کنید؟",
                buttons=[
                    Button.inline("🔙 بازگشت", data=f"{ADMIN_SERVICE_LIST_PREFIX}:{serv_msg.id}"),
                    Button.inline("❌ حذف سرویس", data=f"DeleteServiceAdmin:{service_code}"),
                ],
            )
            return
        try:
            User: UserResponse = await PasarguardAPI(InfoPanel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=InfoPanel.cookie
            )
            service_info_text, primary_subscription_url = await build_service_info_message_text(
                serv_msg, InfoPanel, User
            )
            await set_step(event.sender_id, f"ToServiceAdmin:{serv_msg.code}")
            settings = await SettingsManager().get_settings()
            inline_service = await create_inline_service_buttons(
                services=serv_msg,
                panel=InfoPanel,
                settings=settings,
                admin=True,
                link=f"{primary_subscription_url}",
                status=User.status,
            )
            qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=450x450&data={quote(primary_subscription_url, safe='')}"
            await edit_service_view(
                event,
                service_info_text,
                inline_service,
                qr_url=qr_code_url,
                subscription_link=primary_subscription_url,
                service_code=str(serv_msg.code),
            )

        except HTTPStatusError as e:
            if e.response.status_code == 404:
                err_buttons = [
                    [Button.inline("حذف سرویس", data=f"DeleteServiceAdmin:{serv_msg.code}")],
                    [
                        Button.inline(
                            "بازگشت به لیست سرویس های کاربر ",
                            data=f"{ADMIN_SERVICE_LIST_PREFIX}:{serv_msg.id}",
                        )
                    ],
                ]
                await edit_service_view(
                    event, "خطا: کاربر مورد نظر پیدا نشد. لطفاً نام کاربری را بررسی کنید.", err_buttons
                )
                logger.error("خطا: کاربر مورد نظر پیدا نشد. لطفاً نام کاربری را بررسی کنید.")
            else:
                await event.edit("خطا در دریافت اطلاعات کاربر")
                logger.error(f"خطا در دریافت اطلاعات کاربر: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            await event.edit("خطای غیرمنتظره")
            logger.error(f"خطای غیرمنتظره: {e!s}")

    elif data.startswith("AdminConfigToggle:"):
        service_code = data.split(":")[1]
        _, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not serv_msg:
            await event.answer("سرویس یافت نشد.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return
        try:
            u = await PasarguardAPI(panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=panel.cookie
            )
            new_status = "disabled" if (u.status or "").lower() == "active" else "active"
            await PasarguardAPI(panel.base_url).modify_user_by_id(
                user_id=require_panel_userid(serv_msg),
                user=UserModify(status=new_status),
                token=panel.cookie,
            )
            await event.answer(f"وضعیت: {'غیرفعال' if new_status == 'disabled' else 'فعال'} شد.", alert=True)
        except Exception as e:
            logger.error(f"AdminConfigToggle: {e}")
            await event.answer("خطا در تغییر وضعیت.", alert=True)
        await event.edit(buttons=[[Button.inline("🔄 بروزرسانی", data=f"service_info_admin:{service_code}")]])

    elif data.startswith("AdminConfigVolumeCustom:"):
        service_code = data.split(":")[1]
        await set_data(event.sender_id, "AdminConfigVolumeInputCode", str(service_code))
        await set_step(event.sender_id, "AdminConfigVolumeInput")
        await event.edit(
            "**📦 حجم دلخواه (گیگابایت)**\n\nعدد را ارسال کنید (مثلاً `+10` یا `-3` یا `5` برای +5):",
            buttons=[[Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")]],
        )

    elif data.startswith("AdminConfigVolume:"):
        parts = data.split(":")
        if len(parts) == 2:
            service_code = parts[1]
            await event.edit(
                "**📦 تغییر حجم (ادمین)**\n\nیک گزینه را انتخاب کنید یا مقدار دلخواه:",
                buttons=[
                    [
                        Button.inline("➕ 100 MB", data=f"AdminConfigVolume:{service_code}:+0.1"),
                        Button.inline("➕ 500 MB", data=f"AdminConfigVolume:{service_code}:+0.5"),
                    ],
                    [
                        Button.inline("➕ 1 GB", data=f"AdminConfigVolume:{service_code}:+1"),
                        Button.inline("➕ 5 GB", data=f"AdminConfigVolume:{service_code}:+5"),
                    ],
                    [
                        Button.inline("➖ 100 MB", data=f"AdminConfigVolume:{service_code}:-0.1"),
                        Button.inline("➖ 500 MB", data=f"AdminConfigVolume:{service_code}:-0.5"),
                    ],
                    [
                        Button.inline("➖ 1 GB", data=f"AdminConfigVolume:{service_code}:-1"),
                        Button.inline("➖ 5 GB", data=f"AdminConfigVolume:{service_code}:-5"),
                    ],
                    [Button.inline("✏️ مقدار دلخواه (گیگ)", data=f"AdminConfigVolumeCustom:{service_code}")],
                    [Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")],
                ],
            )
            return
        if len(parts) == 3:
            service_code, op = parts[1], parts[2]
            sign, gb_str = op[0], op[1:] or "0"
            try:
                gb = float(gb_str)
            except ValueError:
                gb = 0.0
            _, serv_msg = await ServiceCRUD().get_service(code=service_code)
            if not serv_msg:
                await event.answer("سرویس یافت نشد.", alert=True)
                return
            panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
            if not panel:
                await event.answer("پنل یافت نشد.", alert=True)
                return
            try:
                u = await PasarguardAPI(panel.base_url).get_user_by_id(
                    user_id=require_panel_userid(serv_msg), token=panel.cookie
                )
                current = int(u.data_limit or 0)
                used = int(getattr(u, "used_traffic", 0) or 0)
                min_limit = used
                delta = int(gb * (1024**3)) * (1 if sign == "+" else -1)
                new_limit = max(min_limit, current + delta)
                if sign == "-" and new_limit == current:
                    await event.answer(
                        f"امکان کسر نیست. حجم مصرف‌شده: {format_size(used, decimal_places=0)}؛ حداکثر {format_size(current - min_limit, decimal_places=0)} قابل کسر است.",
                        alert=True,
                    )
                    return
                await PasarguardAPI(panel.base_url).modify_user_by_id(
                    user_id=require_panel_userid(serv_msg),
                    user=UserModify(data_limit=new_limit),
                    token=panel.cookie,
                )
                await ServiceCRUD().update_service(code=service_code, package_size=new_limit)
                await event.edit(
                    f"✅ حجم به **{format_size(new_limit, decimal_places=0)}** تنظیم شد.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")]],
                )
            except Exception as e:
                logger.error(f"AdminConfigVolume: {e}")
                await event.answer("خطا در تغییر حجم.", alert=True)

    elif data.startswith("AdminConfigTimeCustom:"):
        service_code = data.split(":")[1]
        await set_data(event.sender_id, "AdminConfigTimeInputCode", str(service_code))
        await set_step(event.sender_id, "AdminConfigTimeInput")
        await event.edit(
            "**📅 زمان دلخواه (روز)**\n\nعدد روز را ارسال کنید (مثلاً `+30` یا `-7` یا `14` برای +14 روز):",
            buttons=[[Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")]],
        )

    elif data.startswith("AdminConfigTime:"):
        parts = data.split(":")
        if len(parts) == 2:
            service_code = parts[1]
            await event.edit(
                "**📅 تغییر زمان (ادمین)**\n\nیک گزینه را انتخاب کنید یا روز دلخواه:",
                buttons=[
                    [
                        Button.inline("➕ 1 روز", data=f"AdminConfigTime:{service_code}:+1"),
                        Button.inline("➕ 7 روز", data=f"AdminConfigTime:{service_code}:+7"),
                    ],
                    [
                        Button.inline("➖ 1 روز", data=f"AdminConfigTime:{service_code}:-1"),
                        Button.inline("➖ 7 روز", data=f"AdminConfigTime:{service_code}:-7"),
                    ],
                    [Button.inline("✏️ روز دلخواه", data=f"AdminConfigTimeCustom:{service_code}")],
                    [Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")],
                ],
            )
            return
        if len(parts) == 3:
            service_code, op = parts[1], parts[2]
            sign, days_str = op[0], int(op[1:] or "0")
            _, serv_msg = await ServiceCRUD().get_service(code=service_code)
            if not serv_msg:
                await event.answer("سرویس یافت نشد.", alert=True)
                return
            panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
            if not panel:
                await event.answer("پنل یافت نشد.", alert=True)
                return
            try:
                now_utc = datetime.now(UTC)
                u = await PasarguardAPI(panel.base_url).get_user_by_id(
                    user_id=require_panel_userid(serv_msg), token=panel.cookie
                )
                expire = u.expire if hasattr(u, "expire") and u.expire else now_utc
                if expire.tzinfo is None:
                    expire = expire.replace(tzinfo=UTC)
                delta_d = days_str * (1 if sign == "+" else -1)
                if sign == "-":
                    remaining_days = (expire - now_utc).days
                    if remaining_days <= 0:
                        await event.answer("امکان کسر زمان نیست؛ زمان باقی‌مانده وجود ندارد.", alert=True)
                        return
                    actual_days = min(days_str, remaining_days)
                    new_expire = expire - timedelta(days=actual_days)
                    if new_expire <= now_utc:
                        new_expire = now_utc + timedelta(days=1)
                else:
                    new_expire = expire + timedelta(days=delta_d)
                    if new_expire <= now_utc:
                        new_expire = now_utc + timedelta(days=1)
                await PasarguardAPI(panel.base_url).modify_user_by_id(
                    user_id=require_panel_userid(serv_msg),
                    user=UserModify(expire=new_expire),
                    token=panel.cookie,
                )
                await ServiceCRUD().update_service(code=service_code, expiration_time=int(new_expire.timestamp()))
                await event.edit(
                    f"✅ زمان انقضا به **{timestamp_to_persian_expiry(new_expire.timestamp())}** تنظیم شد.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"service_info_admin:{service_code}")]],
                )
            except Exception as e:
                logger.error(f"AdminConfigTime: {e}")
                await event.answer("خطا در تغییر زمان.", alert=True)

    elif data.startswith("CreateConfigFor:"):
        parts = data.split(":")
        await event.edit("🗳 لطفا حجم سرویس رو وارد کنید به گیگابایت:")
        await set_step(event.sender_id, "CreateConfigFor_GB")
        await set_data(event.sender_id, "UserID", int(parts[1]))

    elif data.startswith("MakeConfig:"):
        parts = data.split(":")
        username_message = await get_bot_text(
            key="enter_username_message",
            default="🔸 یک نام برای کانفیگ وارد کنید:\n^qc^نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.\nنمونه:\nAmir_Kenzo123\nNeda\nNeda123\nNeda_123^qc^",
            lang="fa",
        )
        await event.edit(
            username_message,
            buttons=[Button.inline("🎲 اسم پیشفرض ربات", b"admin_random_username")],
        )
        await set_data(event.sender_id, "AdminPanel", int(parts[1]))
        await set_step(event.sender_id, "admin_enter_username")

    elif data == "admin_random_username":
        panel_code = await get_data(event.sender_id, "AdminPanel")
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        username = await generate_unique_username(panel)
        await delete_message(event, offset=-1)
        await finalize_admin_config(event, username)


async def callback_manage_user_admin(event: events.CallbackQuery.Event):
    data = event.data.decode("UTF-8")
    if await handle_admin_reseller_callbacks(event, data):
        return

    if data.startswith("ToggleSafeMode:"):
        user_id_to_check = int(data.split(":")[1])
        target_user = await UserCRUD().read_user(user_id_to_check)
        if not target_user:
            await event.answer("کاربر یافت نشد.", alert=True)
            return
        current = user_safe_mode_value(target_user)
        new_value = current is not True
        await UserCRUD().update_user(user_id_to_check, safe_mode=new_value)
        status_text = safe_mode_admin_label(new_value)
        await event.answer(
            f"🛡 سیف‌مود برای کاربر `{user_id_to_check}` → {status_text}",
            alert=False,
        )
        await display_user_info_admin(event, user_id_to_check)
        return

    if is_manage_user_service_callback(data):
        await handle_manage_user_service_callbacks(event, data)
        raise events.StopPropagation

    if await get_step(event.sender_id) == "MToUserInfo" and (data.startswith("MToUser_listSv:")):
        Userid = int(data.split(":")[1])

        await display_user_services_Admin(event, Userid, current_page=1, original_event=event, edit_message=True)

    elif await get_step(event.sender_id) == "MToUserInfo" and data.startswith("MToUser_resellers:"):
        user_id = int(data.split(":")[1])
        accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
        if not accounts:
            await event.answer("نمایندگی‌ای یافت نشد.", alert=True)
            return
        await event.edit(
            f"**🏢 نمایندگی‌های کاربر `{user_id}`** ({len(accounts)} مورد)\n\nیک نمایندگی را انتخاب کنید:",
            buttons=build_admin_reseller_list_buttons(user_id, accounts),
            parse_mode="markdown",
        )

    elif data.startswith("AdminSearchConfig:"):
        target_user_id = int(data.split(":")[1])
        await set_data(event.sender_id, "AdminSearchConfigTargetUserId", str(target_user_id))
        await set_step(event.sender_id, "AdminSearchConfig")
        await event.edit(
            "نام کانفیگ (username) را ارسال کنید:",
            buttons=[Button.inline("بازگشت", data=f"BackToUserManagement:{target_user_id}")],
        )

    elif data.startswith("BulkDeleteConfigs:"):
        target_user_id = int(data.split(":")[1])
        await set_data(event.sender_id, "AdminBulkDeleteTargetUserId", str(target_user_id))
        await set_step(event.sender_id, "AdminBulkDeleteConfigs")
        await event.edit(
            "لیست نام کانفیگ‌ها را ارسال کنید (هر خط یک نام):",
            buttons=[Button.inline("بازگشت", data=f"BackToUserManagement:{target_user_id}")],
        )

    elif data.startswith("BackToUserManagement:"):
        Userid = int(data.split(":")[1])
        await delete_data(event.sender_id, "AdminSearchConfigTargetUserId")
        await delete_data(event.sender_id, "AdminBulkDeleteTargetUserId")
        await delete_data(event.sender_id, "AdminBulkDeleteData")
        await event.edit(
            f"شما به عقب بازگشتید\nوضعیت کاربر: {await get_step(Userid)}",
            buttons=await create_inline_manageuser(Userid),
        )
        await set_step(event.sender_id, "MToUserInfo")

    elif data.startswith("BackToServiceListAdmin:"):
        parts = data.split(":")
        admin_user = await UserCRUD().read_user(event.sender_id)
        await display_user_services_Admin(
            event,
            user_id=int(parts[1]),
            current_page=_admin_service_list_page(admin_user.page if admin_user else None),
            edit_message=True,
            original_event=event,
        )

    elif data.startswith("PrevServiceAdmin") or data.startswith("NextServiceAdmin"):
        parts = data.split(":")

        if len(parts) == 3:
            direction = parts[0]
            page = int(parts[1])

            if direction == "PrevServiceAdmin":
                page -= 1
            elif direction == "NextServiceAdmin":
                page += 1

            page = max(1, page)
            await UserCRUD().update_user(user_id=event.sender_id, page=page)

            await display_user_services_Admin(event, int(parts[2]), page, edit_message=True, original_event=event)
        else:
            await event.respond("داده نامعتبر است.")

    elif data.startswith("confirm_phone_"):
        user_id = int(data.replace("confirm_phone_", ""))
        await event.respond(f"لطفا شماره تلفن کاربر ({user_id}) را ارسال کنید:", buttons=Home_Back)
        await set_step(event.sender_id, "confirmUserPhone")
        await set_data(event.sender_id, "confirmPhoneUserId", str(user_id))

    elif data.startswith("BulkDeleteConfirm:"):
        parts = data.split(":")
        if len(parts) != 2:
            await event.answer("Invalid data.", alert=True)
            return
        mode = parts[1]
        if mode not in ("db", "panel", "both"):
            await event.answer("Invalid mode.", alert=True)
            return
        raw = await get_data(event.sender_id, "AdminBulkDeleteData")
        if not raw:
            await event.answer("Session expired or already applied.", alert=True)
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await event.answer("Invalid stored data.", alert=True)
            await delete_data(event.sender_id, "AdminBulkDeleteData")
            return
        target_user_id = int(payload["target_user_id"])
        services = payload.get("services") or []
        db_ok: list[str] = []
        db_fail: list[str] = []
        panel_ok: list[str] = []
        panel_fail: list[tuple[str, str]] = []
        for s in services:
            code = s.get("code")
            username = s.get("username", "")
            in_panel_code = s.get("in_panel")
            on_panel = s.get("on_panel", False)
            if mode in ("db", "both") and code:
                try:
                    await ServiceCRUD().delete_service(code=code)
                    db_ok.append(username)
                except Exception:
                    db_fail.append(username)
            if mode in ("panel", "both") and on_panel and in_panel_code:
                panel = await PanelsManager().get_panel_by_code(code=in_panel_code)
                panel_userid = s.get("panel_userid")
                if panel:
                    try:
                        if not panel_userid:
                            raise ValueError("panel_userid not synced")
                        await PasarguardAPI(base_url=panel.base_url).remove_user_by_id(
                            user_id=int(panel_userid), token=panel.cookie
                        )
                        panel_ok.append(username)
                    except HTTPStatusError as e:
                        panel_fail.append((username, f"HTTP {e.response.status_code}" if e.response else "HTTP error"))
                    except Exception as ex:
                        panel_fail.append((username, str(type(ex).__name__)))
                else:
                    panel_fail.append((username, "panel not found"))
            elif mode in ("panel", "both") and in_panel_code and not on_panel:
                panel_fail.append((username, "was not on panel"))
        await delete_data(event.sender_id, "AdminBulkDeleteData")

        def _block(title: str, items: list, max_show: int = 50) -> str:
            if not items:
                return ""
            head = f"**{title}** ({len(items)})\n"
            if isinstance(items[0], tuple):
                line = "\n".join(f"`{u}` — {reason}" for u, reason in items[:max_show])
            else:
                line = "`, `".join(items[:max_show])
            tail = f"\n_(+{len(items) - max_show} more)_" if len(items) > max_show else ""
            return head + (f"`{line}`" if not isinstance(items[0], tuple) else line) + tail + "\n\n"

        done_parts = [f"👤 کاربر هدف: `{target_user_id}` | حالت: {mode}\n"]
        if mode in ("db", "both"):
            done_parts.append(_block("✅ موفق از دیتابیس", db_ok))
            done_parts.append(_block("❌ ناموفق از دیتابیس", db_fail))
        if mode in ("panel", "both"):
            done_parts.append(_block("✅ موفق از پنل", panel_ok))
            if panel_fail:
                done_parts.append(_block("❌ ناموفق از پنل", panel_fail))
        done_msg = "".join(done_parts).strip() or "حذف گروهی انجام شد."
        if len(done_msg) > 4000:
            done_msg = done_msg[:3990] + "\n\n_(پیام کوتاه شد)_"
        back_btn = [[Button.inline("بازگشت به منوی مدیریت کاربر", data=f"BackToUserManagement:{target_user_id}")]]
        await event.edit(done_msg, buttons=back_btn)

        log_parts = [
            "🗑️ **حذف گروهی کانفیگ**\n\n",
            f"👤 کاربر هدف: `{target_user_id}`\n",
            f"📋 حالت: {mode}\n",
            f"🕒 تاریخ (میلادی): `{Time_Date()['mf']}`\n",
            f"🕒 تاریخ (شمسی): `{Time_Date()['jf']}`\n\n",
        ]
        if mode in ("db", "both"):
            log_parts.append(
                f"**✅ حذف موفق از دیتابیس ({len(db_ok)}):**\n`" + "`, `".join(db_ok) + "`\n\n" if db_ok else ""
            )
            log_parts.append(
                f"**❌ ناموفق از دیتابیس ({len(db_fail)}):**\n`" + "`, `".join(db_fail) + "`\n\n" if db_fail else ""
            )
        if mode in ("panel", "both"):
            log_parts.append(
                f"**✅ حذف موفق از پنل ({len(panel_ok)}):**\n`" + "`, `".join(panel_ok) + "`\n\n" if panel_ok else ""
            )
            if panel_fail:
                log_parts.append("**❌ ناموفق از پنل:**\n" + "\n".join(f"`{u}` — {r}" for u, r in panel_fail) + "\n")
        log_text = "".join(log_parts)
        if len(log_text) > 4000:
            log_text = log_text[:3990] + "\n\n_(لاگ کوتاه شد)_"
        await send_log_message(LogType.OTHER, message=log_text)

    elif data.startswith("UserInfo:"):
        user_id_to_check = int(data.split(":")[1])
        await display_user_info_admin(event, user_id_to_check)

    elif data.startswith("ResetTest:"):
        user_id_to_check = int(data.split(":")[1])
        await UserCRUD().update_user(user_id_to_check, tested=0)
        await event.answer(f"✅ سرویس تست برای کاربر با آیدی `{user_id_to_check}` ریست شد", alert=False)
        await display_user_info_admin(event, user_id_to_check)


def register(client):

    client.add_event_handler(
        callback_manage_user_admin,
        events.CallbackQuery(func=lambda e: e.sender_id in ADMIN_ID),
    )

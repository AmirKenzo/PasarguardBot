"""Message handlers for admin manage_user."""

import json
import re
from datetime import UTC, datetime, timedelta

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI, UserModify
from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.services import ServiceCRUD, get_user_services_paginated
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing.renewal import require_panel_userid
from app.services.reseller.usage_cap import parse_usage_cap_gb, set_reseller_usage_cap
from app.telegram.admin.manage_user.service import build_service_text, finalize_admin_config
from app.telegram.keyboards.admin import build_admin_reseller_account_buttons, create_inline_manageuser
from app.telegram.shared.utils.username import is_valid_username
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from app.telegram.user.reseller.helpers import build_reseller_account_detail_text
from app.utils.formatting.conversions import gigabytes_to_bytes
from app.utils.formatting.dates import timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from config import ADMIN_ID

logger = get_logger(__name__)


async def msg_manage_user_admin(event: Message):
    msg = event.message.text

    if await get_step(event.sender_id) == "panel" and msg == "👤 مدیریت کاربر":
        await event.respond(
            "〰️ لطفا آیدی عددی کاربر را ارسال کنید:", buttons=[Button.text("🔙 بازگشت به پنل", resize=True)]
        )
        await set_step(event.sender_id, "MToUser")

    elif await get_step(event.sender_id) == "AdminResellerUsageCapInput" and msg and msg.strip():
        user_id_raw = await get_data(event.sender_id, "AdminResellerUsageCapUserId")
        code_raw = await get_data(event.sender_id, "AdminResellerUsageCapCode")
        if not user_id_raw or not code_raw:
            await event.respond("نشست منقضی شد.")
            await set_step(event.sender_id, "MToUserInfo")
            return
        gb = parse_usage_cap_gb(msg)
        if gb is None:
            await event.respond("فقط عدد معتبر (گیگابایت) وارد کنید. مثال: `50` یا `0` برای حذف.")
            return
        ok, account = await ResellerAccountCRUD().get_account(int(code_raw))
        target_user_id = int(user_id_raw)
        if not ok or account.telegram_id != target_user_id:
            await event.respond("نمایندگی یافت نشد.")
            await delete_data(event.sender_id, "AdminResellerUsageCapUserId")
            await delete_data(event.sender_id, "AdminResellerUsageCapCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        if account.pricing_mode != "usage":
            await event.respond("سقف مصرف فقط برای پلن مصرفی است.")
            await delete_data(event.sender_id, "AdminResellerUsageCapUserId")
            await delete_data(event.sender_id, "AdminResellerUsageCapCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        success, result_msg = await set_reseller_usage_cap(
            account,
            gigabytes=None if gb <= 0 else gb,
            actor_id=event.sender_id,
            actor_role="ادمین",
        )
        await delete_data(event.sender_id, "AdminResellerUsageCapUserId")
        await delete_data(event.sender_id, "AdminResellerUsageCapCode")
        await set_step(event.sender_id, "MToUserInfo")
        await event.respond(result_msg)
        if success:
            ok, account = await ResellerAccountCRUD().get_account(int(code_raw))
            if ok:
                text = await build_reseller_account_detail_text(account, show_password=False)
                await event.respond(
                    text,
                    buttons=build_admin_reseller_account_buttons(target_user_id, account),
                    parse_mode="markdown",
                )

    elif await get_step(event.sender_id) == "AdminConfigVolumeInput" and msg and msg.strip():
        code_str = await get_data(event.sender_id, "AdminConfigVolumeInputCode")
        if not code_str:
            await event.respond("Session expired.")
            await set_step(event.sender_id, "MToUserInfo")
            return
        s = msg.strip()
        if s.startswith("-"):
            gb = -int((s[1:] or "0").strip())
        elif s.startswith("+"):
            gb = int((s[1:] or "0").strip())
        else:
            try:
                gb = int(s or "0")
            except ValueError:
                await event.respond("عدد معتبر ارسال کنید (مثلاً +10 یا -3 یا 5).")
                return
        if gb == 0:
            await event.respond("عددی غیر از صفر ارسال کنید.")
            return
        _, serv_msg = await ServiceCRUD().get_service(code=int(code_str))
        if not serv_msg:
            await event.respond("سرویس یافت نشد.")
            await delete_data(event.sender_id, "AdminConfigVolumeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not panel:
            await event.respond("پنل یافت نشد.")
            await delete_data(event.sender_id, "AdminConfigVolumeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        try:
            u = await PasarguardAPI(panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=panel.cookie
            )
            current = int(u.data_limit or 0)
            used = int(getattr(u, "used_traffic", 0) or 0)
            min_limit = used
            delta = gigabytes_to_bytes(abs(gb)) * (1 if gb > 0 else -1)
            new_limit = max(min_limit, current + delta)
            if gb < 0 and new_limit == current:
                await event.respond(
                    f"امکان کسر نیست. حجم مصرف‌شده: {format_size(used, decimal_places=0)}؛ حداکثر {format_size(current - min_limit, decimal_places=0)} قابل کسر است."
                )
                return
            await PasarguardAPI(panel.base_url).modify_user_by_id(
                user_id=require_panel_userid(serv_msg),
                user=UserModify(data_limit=new_limit),
                token=panel.cookie,
            )
            await ServiceCRUD().update_service(code=int(code_str), package_size=new_limit)
            await delete_data(event.sender_id, "AdminConfigVolumeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            await event.respond(
                f"✅ حجم به **{format_size(new_limit, decimal_places=0)}** تنظیم شد.",
                buttons=[[Button.inline("🔙 بازگشت به کانفیگ", data=f"service_info_admin:{code_str}")]],
            )
        except Exception as e:
            await event.respond(f"خطا: {e}")

    elif await get_step(event.sender_id) == "AdminConfigTimeInput" and msg and msg.strip():
        code_str = await get_data(event.sender_id, "AdminConfigTimeInputCode")
        if not code_str:
            await event.respond("Session expired.")
            await set_step(event.sender_id, "MToUserInfo")
            return
        s = msg.strip()
        if s.startswith("-"):
            days = -int((s[1:] or "0").strip())
        elif s.startswith("+"):
            days = int((s[1:] or "0").strip())
        else:
            try:
                days = int(s or "0")
            except ValueError:
                await event.respond("عدد معتبر ارسال کنید (مثلاً +30 یا -7 یا 14).")
                return
        if days == 0:
            await event.respond("عددی غیر از صفر ارسال کنید.")
            return
        _, serv_msg = await ServiceCRUD().get_service(code=int(code_str))
        if not serv_msg:
            await event.respond("سرویس یافت نشد.")
            await delete_data(event.sender_id, "AdminConfigTimeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not panel:
            await event.respond("پنل یافت نشد.")
            await delete_data(event.sender_id, "AdminConfigTimeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            return
        try:
            now_utc = datetime.now(UTC)
            u = await PasarguardAPI(panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=panel.cookie
            )
            expire = u.expire if hasattr(u, "expire") and u.expire else now_utc
            if expire.tzinfo is None:
                expire = expire.replace(tzinfo=UTC)
            if days < 0:
                remaining_days = (expire - now_utc).days
                if remaining_days <= 0:
                    await event.respond("امکان کسر زمان نیست؛ زمان باقی‌مانده وجود ندارد.")
                    return
                actual_days = min(abs(days), remaining_days)
                new_expire = expire - timedelta(days=actual_days)
                if new_expire <= now_utc:
                    new_expire = now_utc + timedelta(days=1)
            else:
                new_expire = expire + timedelta(days=days)
                if new_expire <= now_utc:
                    new_expire = now_utc + timedelta(days=1)
            await PasarguardAPI(panel.base_url).modify_user_by_id(
                user_id=require_panel_userid(serv_msg),
                user=UserModify(expire=new_expire),
                token=panel.cookie,
            )
            await ServiceCRUD().update_service(code=int(code_str), expiration_time=int(new_expire.timestamp()))
            await delete_data(event.sender_id, "AdminConfigTimeInputCode")
            await set_step(event.sender_id, "MToUserInfo")
            await event.respond(
                f"✅ زمان انقضا به **{timestamp_to_persian_expiry(new_expire.timestamp())}** تنظیم شد.",
                buttons=[[Button.inline("🔙 بازگشت به کانفیگ", data=f"service_info_admin:{code_str}")]],
            )
        except Exception as e:
            await event.respond(f"خطا: {e}")

    elif await get_step(event.sender_id) == "admin_enter_username" and msg and msg.strip():
        username = msg.strip()
        if not is_valid_username(username):
            await event.respond(
                "❌ نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.",
                buttons=[Button.inline("✨ یه اسم رندوم بده", b"admin_random_username")],
            )
        else:
            await finalize_admin_config(event, username)
        raise events.StopPropagation

    elif await get_step(event.sender_id) == "admin_enter_username" and (not msg or not msg.strip()):
        await event.respond(
            "❌ لطفاً نام کانفیگ را به صورت متن ارسال کنید.",
            buttons=[Button.inline("✨ یه اسم رندوم بده", b"admin_random_username")],
        )
        raise events.StopPropagation

    elif await get_step(event.sender_id) == "CreateConfigFor_GB" and msg:
        if msg.isdigit():
            await event.respond("⌛️ زمان کانفیگ رو به روز وارد کنید:")
            await set_step(event.sender_id, step="GBConfig")
            await set_data(event.sender_id, "GBConfig", int(msg))
        else:
            await event.respond("لطفاً فقط عدد ارسال کنید ❗️❗️")
        raise events.StopPropagation

    elif await get_step(event.sender_id) == "GBConfig" and msg:
        if msg.isdigit():
            await set_step(event.sender_id, step="TimeConfig")
            await set_data(event.sender_id, "TimeConfig", int(msg))
            panels = await PanelsManager().get_all_panels()
            panel_buttons = []
            for panel in panels:
                button = Button.inline(panel.name, data=f"MakeConfig:{panel.code}")
                panel_buttons.append(button)

            panel_rows = [panel_buttons[i : i + 3] for i in range(0, len(panel_buttons), 3)]
            panel_rows.append([Button.inline("❌ انصراف", data="DataCancel")])
            await event.respond("لطفا یکی از پنل های زیر رو برای ساخت کانفیگ انتخاب کنید", buttons=panel_rows)
        else:
            await event.respond("لطفاً فقط عدد ارسال کنید ❗️❗️")
        raise events.StopPropagation

    elif (
        await get_step(event.sender_id) == "AdminBulkDeleteConfigs"
        and msg
        and msg.strip()
        and msg != "🔙 بازگشت به پنل"
    ):
        target_user_id_str = await get_data(event.sender_id, "AdminBulkDeleteTargetUserId")
        if not target_user_id_str:
            await event.respond("Session expired. Use Back and try again.")
            await set_step(event.sender_id, "MToUserInfo")
            return
        try:
            target_user_id = int(target_user_id_str)
        except TypeError, ValueError:
            await event.respond("Invalid session.")
            await delete_data(event.sender_id, "AdminBulkDeleteTargetUserId")
            await set_step(event.sender_id, "MToUserInfo")
            return
        requested = [line.strip() for line in msg.strip().splitlines() if line.strip()]
        if not requested:
            await event.respond("لیست خالی است. حداقل یک نام ارسال کنید.")
            return
        name_to_service = {}
        services_list = await ServiceCRUD().get_services_by_user_and_usernames(target_user_id, requested)
        if not services_list:
            services_list = await ServiceCRUD().get_services_by_usernames(requested)
            services_list = [s for s in services_list if s.id is None or s.id == target_user_id]
        for s in services_list:
            if s.username:
                name_to_service[(s.username or "").strip()] = s
        in_db = list(name_to_service.keys())
        not_in_db = [n for n in requested if n not in name_to_service]
        services_with_panel = []
        for _username, s in name_to_service.items():
            panel = await PanelsManager().get_panel_by_code(code=s.in_panel)
            on_panel = False
            if panel and s.panel_userid:
                try:
                    await PasarguardAPI(base_url=panel.base_url).get_user_by_id(
                        user_id=int(s.panel_userid), token=panel.cookie
                    )
                    on_panel = True
                except HTTPStatusError as e:
                    if e.response.status_code != 404:
                        on_panel = False
                except Exception:
                    on_panel = False
            services_with_panel.append(
                {
                    "code": s.code,
                    "username": s.username,
                    "in_panel": s.in_panel,
                    "on_panel": on_panel,
                    "panel_userid": s.panel_userid,
                }
            )
        on_panel_list = [x["username"] for x in services_with_panel if x["on_panel"]]
        not_on_panel_list = [x["username"] for x in services_with_panel if not x["on_panel"]]

        def _fmt(names: list, max_show: int = 30) -> str:
            if not names:
                return "—"
            s = "`, `".join(names[:max_show])
            return f"`{s}`" + (f" (+{len(names) - max_show} more)" if len(names) > max_show else "")

        report_lines = [
            f"**در دیتابیس ربات (برای این کاربر):** {len(in_db)} عدد",
            _fmt(in_db),
            "",
            f"**روی پنل هست:** {len(on_panel_list)} عدد",
            _fmt(on_panel_list),
            "",
            f"**روی پنل نیست:** {len(not_on_panel_list)} عدد",
            _fmt(not_on_panel_list),
            "",
            f"**در دیتابیس نبود:** {len(not_in_db)} عدد",
            _fmt(not_in_db),
        ]
        report_text = "\n".join(report_lines)
        payload = {"target_user_id": target_user_id, "services": services_with_panel}
        await set_data(event.sender_id, "AdminBulkDeleteData", json.dumps(payload, ensure_ascii=False))
        await delete_data(event.sender_id, "AdminBulkDeleteTargetUserId")
        await set_step(event.sender_id, "MToUserInfo")
        await event.respond(
            report_text,
            buttons=[
                [
                    Button.inline("حذف فقط از دیتابیس", data="BulkDeleteConfirm:db"),
                    Button.inline("حذف فقط از پنل", data="BulkDeleteConfirm:panel"),
                ],
                [Button.inline("حذف از پنل و دیتابیس", data="BulkDeleteConfirm:both")],
                [Button.inline("بازگشت", data=f"BackToUserManagement:{target_user_id}")],
            ],
        )

    elif await get_step(event.sender_id) == "AdminSearchConfig" and msg and msg != "🔙 بازگشت به پنل":
        target_user_id_str = await get_data(event.sender_id, "AdminSearchConfigTargetUserId")
        if not target_user_id_str:
            await event.respond("Session expired. Use Back and try again.")
            await set_step(event.sender_id, "MToUserInfo")
            return
        try:
            target_user_id = int(target_user_id_str)
        except TypeError, ValueError:
            await event.respond("Invalid session.")
            await delete_data(event.sender_id, "AdminSearchConfigTargetUserId")
            await set_step(event.sender_id, "MToUserInfo")
            return
        services, total = await get_user_services_paginated(
            user_id=target_user_id, page=1, limit=25, search=msg.strip()
        )
        if not services:
            await event.respond("کانفیگی با این نام یافت نشد.")
            return
        display_user = await UserCRUD().read_user(event.sender_id)
        if not display_user:
            display_user = await UserCRUD().read_user(target_user_id)
        if not display_user:
            await event.respond("User not found.")
            await delete_data(event.sender_id, "AdminSearchConfigTargetUserId")
            await set_step(event.sender_id, "MToUserInfo")
            return
        service_buttons = []
        for s in services:
            PanelName = await PanelsManager().get_panel_by_code(code=s.in_panel)
            panel_display_name = PanelName.name if PanelName else "?"
            text = await build_service_text(s, panel_display_name, display_user)
            service_buttons.append([Button.inline(text, data=f"service_info_admin:{s.code}")])
        back_btn = [Button.inline("بازگشت", data=f"BackToUserManagement:{target_user_id}")]
        await event.respond(
            f"تعداد {total} کانفیگ یافت شد. برای باز کردن کلیک کنید:",
            buttons=[*service_buttons, back_btn],
        )
        await delete_data(event.sender_id, "AdminSearchConfigTargetUserId")
        await set_step(event.sender_id, "MToUserInfo")

    elif await get_step(event.sender_id) == "MToUser" and msg != "🔙 بازگشت به پنل":
        if msg.isdigit():
            user_id = int(msg)
            founded = await UserCRUD().read_user(user_id)
            if founded:
                await event.respond(
                    f"▪️ لطفا از دکمه های زیر انتخاب کنید:\nوضعیت کاربر: {await get_step(user_id)}",
                    buttons=await create_inline_manageuser(user_id),
                )

                await set_step(event.sender_id, "MToUserInfo")
            else:
                await event.respond("یوزر یافت نشد.")
        else:
            await event.respond("⚠️ فقط ID عددی ارسال کنید.")

    elif await get_step(event.sender_id) == "confirmUserPhone" and msg:
        if msg in ["🏠", "/start", "/panel"]:
            await delete_data(event.sender_id, "confirmPhoneUserId")
            await set_step(event.sender_id, "panel")
            await event.respond("تایید شماره لغو شد.")
            return

        target_user_id_str = await get_data(event.sender_id, "confirmPhoneUserId")
        if not target_user_id_str:
            await event.respond("خطا: شناسه کاربر یافت نشد.")
            await delete_data(event.sender_id, "confirmPhoneUserId")
            await set_step(event.sender_id, "panel")
            return

        try:
            target_user_id = int(target_user_id_str)
        except TypeError, ValueError:
            await event.respond("شناسه کاربر نامعتبر است.")
            await delete_data(event.sender_id, "confirmPhoneUserId")
            await set_step(event.sender_id, "panel")
            return

        phone_number = msg.strip()
        digits_only = re.sub(r"\D+", "", phone_number)

        if digits_only.startswith("0") and len(digits_only) == 11:
            phone_number = "+98" + digits_only[1:]
        elif digits_only.startswith("98") and len(digits_only) >= 12:
            phone_number = "+" + digits_only
        elif len(digits_only) >= 10:
            phone_number = "+98" + digits_only if len(digits_only) == 10 else "+98" + digits_only[-10:]
        else:
            await event.respond("⚠️ فرمت شماره تلفن نامعتبر است. لطفا شماره را به درستی وارد کنید.")
            return

        success = await UserCRUD().update_user(user_id=target_user_id, number=phone_number)
        if success:
            await event.respond(
                f"✅ شماره تلفن کاربر ({target_user_id}) با موفقیت به‌روزرسانی شد.\n📱 شماره: {phone_number}"
            )
        else:
            await event.respond(f"❌ خطا در بروزرسانی شماره تلفن کاربر ({target_user_id}).")

        await delete_data(event.sender_id, "confirmPhoneUserId")
        await set_step(event.sender_id, "panel")


def register(client):

    client.add_event_handler(
        msg_manage_user_admin,
        events.NewMessage(incoming=True, from_users=ADMIN_ID),
    )

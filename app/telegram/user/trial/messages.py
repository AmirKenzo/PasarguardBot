"""Message handlers for free trial (/start free deep link, menu button)."""

from __future__ import annotations

import random
import time

from pasarguard import PasarguardAPI, UserCreate
from pasarguard.enums import UserDataLimitResetStrategy
from telethon import Button, events
from telethon.tl.custom import Message
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.services.panels.auth import fetch_panel_groups_with_auth
from app.services.panels.config_links import get_selected_single_config_links_text
from app.services.panels.settings import panel_test_duration_days, panel_test_volume_gb
from app.services.subscriptions.links import format_subscription_links_for_message
from app.telegram.keyboards.common import is_keyboard_config_step, styled_copy_button, styled_webview_button
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.channel_gate import ensure_channel_membership, extract_start_param
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.media import respond_with_photo_and_text
from app.telegram.state import get_step, set_step
from app.telegram.user.trial.helpers import _resolve_panel_group_ids, _user_lang
from app.utils.formatting.conversions import convert_storage, day_to_timestamp, gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.media.qrcode import create_qr_code
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def free_trial_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) == "ban":
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False

    msg = event.message.text or event.message.message or ""
    if not msg:
        return False

    param = extract_start_param(event)
    if param and param.lower() == "free":
        return True
    menu_text = await get_button_text("bt.menu_get_trial", "🎁 دریافت تست")
    return msg in {menu_text, "🎁 دریافت تست"}


@bot_is_offline
async def free_trial_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    lang = await _user_lang(user_id)
    paneltest = await SettingsManager().get_settings()
    if paneltest.test_mode == 0:
        await event.respond("😢 دریافت تست از سمت ادمین غیرفعال شده", buttons=await bhome_buttons(user_id, lang))
        raise events.StopPropagation
    if paneltest.test_panel_id == 0:
        await event.respond("پنل برای دریافت تست موجود نیست", buttons=await bhome_buttons(user_id, lang))
        raise events.StopPropagation
    if paneltest.test_panel_id is None:
        raise events.StopPropagation

    try:
        tested = await UserCRUD().read_user(user_id=user_id)

        test_phone_verify = getattr(paneltest, "test_phone_verify", True)
        if test_phone_verify and (
            not tested.number or not (tested.number.startswith("+98") or tested.number.startswith("98"))
        ):
            await event.respond(
                "🔐 برای دریافت تست رایگان، ابتدا باید شماره تلفن خود را تایید کنید.\n\n"
                "👈 لطفاً شماره تماس مرتبط با اکانت خود را از طریق دکمه زیر به اشتراک بگذارید.\n\n"
                "✅ توجه: شماره شما کاملاً محرمانه بوده و صرفاً برای اطمینان از صحت اطلاعات و ارائه خدمات بهتر استفاده خواهد شد.",
                buttons=[[Button.request_phone("📱 ارسال شماره تلفن", resize=True, single_use=True)]],
            )
            await set_step(user_id=user_id, step="test_phone_verify")
            raise events.StopPropagation

        if tested.tested != 0:
            await event.respond(
                "😢 دوست عزیز شما قبلا تست خودتون رو گرفتید",
                buttons=await bhome_buttons(user_id, lang),
            )
            raise events.StopPropagation

        paneltest = await SettingsManager().get_settings()
        panel = await PanelsManager().get_panel_by_code(code=paneltest.test_panel_id)
        test_volume_gb = panel_test_volume_gb(panel)
        test_duration_days = panel_test_duration_days(panel)

        code_service = random.randint(10000, 9999999)
        await UserCRUD().update_user(user_id=user_id, tested=1)
        username = f"test_{code_service}"
        groups_resp = await fetch_panel_groups_with_auth(panel)
        group_ids: list[int] = _resolve_panel_group_ids(panel, groups_resp)

        start_time = time.time()
        new_user = UserCreate(
            username=username,
            group_ids=group_ids,
            data_limit=gigabytes_to_bytes(float(test_volume_gb)),
            expire=day_to_timestamp(int(test_duration_days)),
            note=f"{user_id}\ntest",
            data_limit_reset_strategy=UserDataLimitResetStrategy.NO_RESET,
        )
        added_user = await PasarguardAPI(panel.base_url).add_user(user=new_user, token=panel.cookie)

        creation_time = time.time() - start_time
        if creation_time < 1:
            creation_time_text = f"{creation_time * 1000:.0f}"
            creation_time_unit = "میلی‌ثانیه"
        else:
            creation_time_text = f"{creation_time:.2f}"
            creation_time_unit = "ثانیه"

        subscription_url = added_user.subscription_url
        subscription_url = (
            subscription_url if subscription_url.startswith("http") else f"{panel.base_url}{subscription_url}"
        )
        subscription_links_text, primary_subscription_url = format_subscription_links_for_message(
            panel,
            subscription_url,
            main_label="🔗 لینک اختصاصی",
            tunnel_label="🌐 لینک تانل اختصاصی",
        )
        single_config_links_text = await get_selected_single_config_links_text(
            panel,
            getattr(added_user, "id", None),
        )
        single_config_links_section = (
            f"**🔗 لینک‌های تکی انتخاب‌شده:**\n{single_config_links_text}" if single_config_links_text else ""
        )
        qr_file = create_qr_code(text=f"{primary_subscription_url}", filename=f"{code_service}.png")
        volume_text = convert_storage(test_volume_gb)

        txt_template = await get_bot_text(
            key="test_config_delivery_message",
            default=(
                "**🎉 کانفیگ اختصاصی V2Ray شما در عرض فقط {creation_time} توسط ربات ساخته شد . !**\n"
                "🌐 نام پنل 🧪 تست\n"
                "**#️⃣ کد سرویس(در ربات):** `{service_code}`\n"
                "**🔷 اسم کانفیگ:** `{account_name}`\n"
                "**📥 حجم تست:** {test_volume}\n"
                "**⏰ مدت زمان :** {test_duration} روز (تست رایگان)\n"
                "**🔗 لینک اختصاصی شما:**\n\n"
                "`{subscription_url}`\n"
                "{config_links_with_txt}\n"
            ),
            lang="fa",
        )
        txt_template = txt_template.replace("`{subscription_url}`", "{subscription_url}")
        txt = (
            txt_template.replace("{creation_time}", f"{creation_time_text} {creation_time_unit}")
            .replace("{service_code}", str(code_service))
            .replace("{account_name}", username)
            .replace("{test_volume}", volume_text)
            .replace("{test_duration}", str(test_duration_days))
            .replace("{subscription_url}", subscription_links_text)
            .replace("{config_links}", single_config_links_text)
            .replace("{config_links_with_txt}", single_config_links_section)
        )

        try:
            telegram_user = await Kenzo.get_entity(user_id)
            user_first_name = telegram_user.first_name or "نامشخص"
            user_last_name = telegram_user.last_name or ""
            user_full_name = f"{user_first_name} {user_last_name}".strip()
            user_username = telegram_user.username or "ندارد"
        except Exception:
            user_full_name = "نامشخص"
            user_username = "ندارد"

        log_text = (
            f"📢 ** دریافت تست رایگان **\n\n"
            f"**👤 اطلاعات کاربر:**\n"
            f"**📝 نام:** {user_full_name}\n"
            f"**#⃣ آیدی کاربر:** `{user_id}` | [پروفایل کاربر](tg://user?id={user_id})\n"
            f"**📱 یوزرنیم:** @{user_username}\n\n"
            f"**📦 اطلاعات تست:**\n"
            f"**📥 حجم تست:** {volume_text}\n"
            f"**⏰ زمان تست:** {test_duration_days} روز\n\n"
            f"**📅 تاریخ (میلادی):** `{Time_Date()['mf']}`\n"
            f"**📅 تاریخ (شمسی):** `{Time_Date()['jf']}`\n"
            f"**🎫 کد سرویس:** `{code_service}`\n"
            f"**🔷 اسم کانفیگ:** `{username}`\n"
            f"**🎫 کد پنل:** `{panel.code}`\n"
            f"**🌐 نام پنل:** `{panel.name}`\n"
            f"**🔗 لینک کانفیگ:**\n{subscription_links_text}"
        )

        trial_buttons = ReplyInlineMarkup(
            [
                KeyboardInlineButtonRow(
                    [
                        styled_webview_button(
                            "برای مشاهده اطلاعات بیشتر کلیک کنید",
                            f"{primary_subscription_url}",
                        )
                    ]
                ),
                KeyboardInlineButtonRow([styled_copy_button("برای کپی لینک کلیک کنید", f"{primary_subscription_url}")]),
            ]
        )
        await respond_with_photo_and_text(
            event,
            file=qr_file,
            text=txt,
            short_caption=(
                f"**🎉 کانفیگ تست شما ساخته شد** (#{code_service})\n"
                f"**🔷 اسم کانفیگ:** `{username}`\n"
                f"🔗 `{primary_subscription_url}`"
            ),
            buttons=trial_buttons,
        )

        await ServiceCRUD().create_service(
            code=code_service,
            username=username,
            enable=1,
            in_panel=panel.code,
            panel_userid=getattr(added_user, "id", None),
            id=user_id,
            package_size=gigabytes_to_bytes(float(test_volume_gb)),
            createtime=Time_Date()["stamp"],
            expiration_time=day_to_timestamp(int(test_duration_days)),
            is_test=True,
        )

        await send_log_message(LogType.OTHER, message=log_text)

    except events.StopPropagation:
        raise
    except Exception as exc:
        logger.error("%s", exc)

    raise events.StopPropagation


async def trial_phone_verify_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if not event.message.contact:
        return False
    return await get_step(event.sender_id) == "test_phone_verify"


@bot_is_offline
async def trial_phone_verify_handler(event: Message):
    contact = event.message.contact
    user_id = event.sender_id
    lang = await _user_lang(user_id)
    user = await event.get_sender()
    username = user.username if user.username else "یوزرنیم موجود نیست"
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    phone_number = contact.phone_number

    if contact.user_id != user_id:
        await event.respond(
            "🚫 فقط می‌توانید شماره تلفن متعلق به خودتان را ارسال کنید.\n❌ ارسال شماره‌های دیگر مجاز نیست."
        )
        log_message = (
            f"❌ شماره تایید نشد\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)
        raise events.StopPropagation

    if phone_number.startswith("+98") or phone_number.startswith("98"):
        log_message = (
            f"🔐 احراز هویت جدیدی انجام شد.\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

        success = await UserCRUD().update_user(user_id=user_id, number=phone_number)
        if success:
            txt = (
                "✅ شماره تلفن شما با موفقیت ثبت شد.\n"
                "🌟 از اعتماد شما به مجموعه ما سپاسگزاریم! ما متعهد به حفظ حریم خصوصی و ارائه بهترین خدمات به شما هستیم.\n"
                "📌 در صورت نیاز به پشتیبانی، همواره می‌توانید با ما در تماس باشید. 🙏\n"
            )
            await event.respond(txt, buttons=await bhome_buttons(user_id, lang))
            await set_step(user_id=user_id, step="start")
        else:
            await event.respond(
                "⛔ متأسفیم! خطایی در به‌روزرسانی شماره تلفن شما رخ داد.\n"
                "لطفاً دوباره تلاش کنید یا در صورت ادامه مشکل، با پشتیبانی تماس بگیرید. 🙏"
            )
            log_message = (
                f"⛔ خطا\n\n"
                f"▪️ آیدی عددی : {user_id}\n"
                f"❕ نام پروفایل : {full_name}\n"
                f"☎️ یوزرنیم : @{username}\n"
                f"☎️ شماره تلفن : {phone_number}\n\n"
                "⛔ متأسفیم! خطایی در به‌روزرسانی شماره تلفن شما رخ داد.\n"
                "لطفاً دوباره تلاش کنید یا در صورت ادامه مشکل، با پشتیبانی تماس بگیرید. 🙏"
            )
            await send_log_message(LogType.OTHER, message=log_message)
    else:
        await event.respond(
            "🚫 فقط شماره‌هایی که با پیش‌شماره +98 شروع می‌شوند قابل پذیرش هستند.\n"
            "👈 لطفاً یک شماره معتبر ایرانی وارد کنید."
        )
        log_message = (
            f"❌ شماره تایید نشد\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        free_trial_handler,
        events.NewMessage(incoming=True, func=free_trial_filter),
    )
    client.add_event_handler(
        trial_phone_verify_handler,
        events.NewMessage(incoming=True, func=trial_phone_verify_filter),
    )

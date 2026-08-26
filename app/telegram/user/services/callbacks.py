"""Callback handlers for user service management flow."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI, ProxySettings, UserModify, UserResponse
from telethon import Button, events
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, update_Money
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_flow import (
    build_insufficient_balance_message,
    create_direct_pay_balance_button,
    is_direct_pay_renew_enabled,
    mark_direct_pay_ready,
)
from app.services.billing.direct_pay_store import KIND_RENEW, cancel_pending_for_user
from app.services.billing.renewal import (
    apply_panel_user_renewal,
    preview_remaining_after_renewal,
    require_panel_userid,
)
from app.services.panels.config_links import fetch_user_config_links
from app.services.panels.settings import (
    get_panel_time_plan,
    get_panel_volume_plan,
    panel_display_mode,
    panel_has_time_plans,
    panel_has_volume_plans,
    panel_time_plans,
    panel_volume_plans,
)
from app.services.subscriptions.links import (
    build_tunnel_subscription_url,
    format_subscription_links_for_message,
    resolve_subscription_display_urls,
)
from app.telegram.keyboards.buy import (
    build_ms_renew_confirm_button_rows,
    ms_renew_back_button,
)
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.keyboards.services import create_inline_service_buttons
from app.telegram.shared.guards.callback_guards import notify_session_expired, run_service_callback_guards
from app.telegram.shared.keyboards.panel_buttons import (
    build_time_upgrade_select_buttons,
    build_time_upgrade_tariff_text,
    build_volume_upgrade_select_buttons,
    build_volume_upgrade_tariff_text,
)
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from app.telegram.user.services.helpers import (
    SERVICE_CALLBACK_PREFIXES,
    _back_to_service,
    _deny_unless_service_owner_or_admin,
    build_service_info_message_text,
    check_user_balance,
    create_balance_button,
    display_subscription_clients,
    display_subscription_links,
    display_usage_chart,
    display_usage_chart_day,
    display_user_services,
    edit_service_view,
    generate_volume_buttons_tamdid,
    group_durations,
)
from app.telegram.user.services.states import BOT_LANGUAGE, SUB_LINKS_PAGE_LIMIT
from app.utils.formatting.conversions import convert_storage, day_to_timestamp, gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_ip_limit, format_size
from app.utils.media.qrcode import create_qr_code
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID

logger = get_logger(__name__)


async def service_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if not event.data:
        return False
    data = event.data.decode("utf-8", "ignore")
    if data == "Confirm_buy_tamdid" or data in {"BackToServiceList", "BackToServiceListFromCredential"}:
        return True
    if data.startswith(("PrevService", "NextService")):
        return True
    return data.startswith(SERVICE_CALLBACK_PREFIXES)


@bot_is_offline
async def service_callback_handler(event: events.CallbackQuery.Event, data: str | None = None):
    data = data or event.data.decode("utf-8", "ignore")

    if not await run_service_callback_guards(event, data):
        return

    info = await UserCRUD().read_user(event.sender_id)
    lang = info.language if info and info.language else BOT_LANGUAGE

    if data.startswith("TamdidVPN_"):
        selected_code = data.replace("TamdidVPN_", "")
        _step = (await get_step(event.sender_id)) or ""
        if _step.startswith("ToServiceAdmin:"):
            await set_data(event.sender_id, "from_admin", "1")
        sts, result = await ServiceCRUD().get_service(code=selected_code)

        if sts:
            if await _deny_unless_service_owner_or_admin(event, result):
                return
            if getattr(result, "is_test", False) is True:
                await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
                return
            # Cancel leftover buy pendings; renew pending is created only after insufficient + topup.
            await cancel_pending_for_user(event.sender_id)
            panel_manager = PanelsManager()
            panel = await panel_manager.get_panel_by_code(result.in_panel)
            display_mode = panel_display_mode(panel) if panel else "classic"

            is_fair_usage = False
            if result.package_size:
                current_plan = await PlanManager().get_plan_by_volume_for_display(
                    gb=result.package_size / (1024**3), panel_code=result.in_panel
                )
                if (
                    current_plan
                    and hasattr(current_plan, "plan_type")
                    and current_plan.plan_type in ["fair_usage", "fair"]
                ):
                    is_fair_usage = True

            if display_mode == "duration_first":
                durations = await PlanManager().get_unique_durations(result.in_panel)

                if not durations:
                    await event.answer("❌ هیچ پلنی برای این پنل موجود نیست!", alert=True)
                    return

                duration_groups = group_durations(durations)

                if not duration_groups:
                    await event.answer("❌ هیچ پلنی برای این پنل موجود نیست!", alert=True)
                    return

                if is_fair_usage:
                    renewal_text = (
                        "✨ تمدید سرویس نامحدود (مصرف منصفانه)\n"
                        "**🔹 با تمدید سرویس نامحدود:**\n"
                        "**حجم مصرفی** ریست شده و صفر می‌شود (می‌توانید مجدداً استفاده کنید).\n"
                        "**زمان اشتراک** از ابتدا محاسبه شده و جایگزین می‌شود.\n\n"
                        "🔸 مثال: اگر پلن روزانه 10 گیگ دارید و امروز 10 گیگ مصرف کرده‌اید:\n"
                        "با تمدید، **حجم مصرفی ریست** می‌شود و می‌توانید دوباره از سرویس استفاده کنید.\n"
                        "**زمان:** به مدت پلن جدید تمدید می‌شود.\n\n"
                        ""
                    )
                    duration_message_tamdid = await get_bot_text(
                        key="buy_select_duration_message",
                        default="⚡️ یکی از پلن های موجود رو از ۷ روزه تا ۹۰ روزه انتخاب کن :",
                        lang="fa",
                    )
                    renewal_text += f"**{duration_message_tamdid}**"
                else:
                    renewal_text = await get_bot_text(
                        key="renewal_step_one_text",
                        default=(
                            "🌐 مرحله اول تمدید اکانت :\n\n"
                            "📆 زمان اشتراک خود را انتخاب کنید:\n\n"
                            "‼️نکته مهم :\n\n"
                            "❌ با تمدید سرویس حجم باقی‌مانده اشتراک شما به دوره جدید اضافه میشه و نمیسوزه ولی زمان اشتراک ریست میشه و از ابتدا محاسبه میشه.\n\n"
                            "🔑 مثال: اگر 2 گیگ و 8 روز از اکانت شما باقی مونده باشه و پلنی که انتخاب کردید 100 گیگ 30 روزه باشه بعد از تمدید مشخصات اکانت شما به شکل زیر خواهد شد:\n\n"
                            "📥 مثال حجم جدید: 102 گیگ می‌شود.\n"
                            "⏰ مثال زمان جدید: 30 روزه میشود.\n\n"
                            "✅ حالا برای تمدید زمان اکانتت یکی از پلن های موجود رو از ۷ روزه تا ۹۰ روزه انتخاب کن :👇"
                        ),
                        lang="fa",
                    )

                from app.telegram.shared.keyboards.duration_buttons import build_duration_selection_button_rows

                _back_tamdid = await _back_to_service(event.sender_id, str(result.code))
                duration_buttons = await build_duration_selection_button_rows(
                    result.in_panel,
                    duration_groups,
                    context="tamdid",
                    make_callback=lambda d: f"SelectDurationGroupForTamdid:{result.code}:{d}",
                    back_row=[await ms_renew_back_button(_back_tamdid)],
                )

                await event.edit(
                    renewal_text,
                    buttons=duration_buttons,
                )
                await set_data(event.sender_id, "ConfigID", selected_code)
            else:
                if is_fair_usage:
                    renewal_text = (
                        "✨ تمدید سرویس نامحدود (مصرف منصفانه)\n"
                        "**🔹 با تمدید سرویس نامحدود:**\n"
                        "**حجم مصرفی** ریست شده و صفر می‌شود (می‌توانید مجدداً استفاده کنید).\n"
                        "**زمان اشتراک** از ابتدا محاسبه شده و جایگزین می‌شود.\n\n"
                        "🔸 مثال: اگر پلن روزانه 10 گیگ دارید و امروز 10 گیگ مصرف کرده‌اید:\n"
                        "با تمدید، **حجم مصرفی ریست** می‌شود و می‌توانید دوباره از سرویس استفاده کنید.\n"
                        "**زمان:** به مدت پلن جدید تمدید می‌شود.\n\n"
                        "**👇 یکی از گزینه‌ها را انتخاب کنید:**"
                    )
                else:
                    renewal_text = await get_bot_text(
                        key="renewal_step_one_text",
                        default=(
                            "🌐 مرحله اول تمدید اکانت :\n\n"
                            "📆 زمان اشتراک خود را انتخاب کنید:\n\n"
                            "‼️نکته مهم :\n\n"
                            "❌ با تمدید سرویس حجم باقی‌مانده اشتراک شما به دوره جدید اضافه میشه و نمیسوزه ولی زمان اشتراک ریست میشه و از ابتدا محاسبه میشه.\n\n"
                            "🔑 مثال: اگر 2 گیگ و 8 روز از اکانت شما باقی مونده باشه و پلنی که انتخاب کردید 100 گیگ 30 روزه باشه بعد از تمدید مشخصات اکانت شما به شکل زیر خواهد شد:\n\n"
                            "📥 مثال حجم جدید: 102 گیگ می‌شود.\n"
                            "⏰ مثال زمان جدید: 30 روزه میشود.\n\n"
                            "✅ حالا برای تمدید زمان اکانتت یکی از پلن های موجود رو از ۷ روزه تا ۹۰ روزه انتخاب کن :👇"
                        ),
                        lang="fa",
                    )

                await set_step(event.sender_id, "selectTamdid")
                await set_data(event.sender_id, "ConfigID", selected_code)
                await event.edit(
                    renewal_text,
                    buttons=await generate_volume_buttons_tamdid(config_code=result.code, sender_id=event.sender_id),
                )

            await set_data(event.sender_id, "panel", result.in_panel)

    elif data.startswith("SelectDurationGroupForTamdid:"):
        parts = data.split(":")
        config_code = parts[1]
        duration_value = int(parts[2])

        sts, result = await ServiceCRUD().get_service(code=config_code)
        if not sts:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return

        is_fair_usage = False
        if result.package_size:
            current_plan = await PlanManager().get_plan_by_volume_for_display(
                gb=result.package_size / (1024**3), panel_code=result.in_panel
            )
            if current_plan and hasattr(current_plan, "plan_type") and current_plan.plan_type in ["fair_usage", "fair"]:
                is_fair_usage = True

        if is_fair_usage:
            renewal_text = (
                "✨ تمدید سرویس نامحدود (مصرف منصفانه)\n"
                f"**⏰ مدت زمان انتخاب شده: {duration_value} روزه**\n\n"
                "**🔹 با تمدید سرویس نامحدود:**\n"
                "**حجم مصرفی** ریست شده و صفر می‌شود (می‌توانید مجدداً استفاده کنید).\n"
                "**زمان اشتراک** از ابتدا محاسبه شده و جایگزین می‌شود.\n\n"
                "🔸 مثال: اگر پلن روزانه 10 گیگ دارید و امروز 10 گیگ مصرف کرده‌اید:\n"
                "با تمدید، **حجم مصرفی ریست** می‌شود و می‌توانید دوباره از سرویس استفاده کنید.\n"
                "**زمان:** به مدت پلن جدید تمدید می‌شود.\n\n"
                "**📥 حجم بسته خودتان را انتخاب کنید:**"
            )
        else:
            # Get panel name
            panel = await PanelsManager().get_panel_by_code(result.in_panel)
            panel_name = panel.name if panel else "پنل"

            # Get renewal text from database with placeholders
            renewal_text_template = await get_bot_text(
                key="renewal_step_two_text",
                default=(
                    "✅ مرحله دوم تمدید اکانت : {panel_name}\n\n"
                    "🗓 مدت زمانی که برای این اکانت انتخاب کردید {duration} است !\n\n"
                    "📥 در این مرحله یکی از پلن های زیر را انتخاب کنید :"
                ),
                lang="fa",
            )

            # Replace placeholders
            renewal_text = renewal_text_template.replace("{duration}", f"{duration_value} روزه").replace(
                "{panel_name}", panel_name
            )

        await event.edit(
            renewal_text,
            buttons=await generate_volume_buttons_tamdid(
                config_code=result.code, duration_group=[duration_value], sender_id=event.sender_id
            ),
        )
        await set_step(event.sender_id, "selectTamdid")

    elif data.startswith("SelectPlanTamdid_"):
        if await get_step(event.sender_id) != "selectTamdid":
            await notify_session_expired(event)
            return
        try:
            plan_id = int(data.split("_")[-1])
        except ValueError:
            await event.answer("❌ پلن نامعتبر است.", alert=True)
            return

        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("❌ پلن یافت نشد!", alert=True)
            return

        await set_step(event.sender_id, "crconf_tamdid")

        await set_data(event.sender_id, "gig", plan.storage)
        await set_data(event.sender_id, "selected_plan_id", plan_id)

        ConfigID = await get_data(event.sender_id, "ConfigID")
        service, serv_msg = await ServiceCRUD().get_service(code=ConfigID)
        if not service:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return

        panel_code = await get_data(event.sender_id, "panel") or serv_msg.in_panel
        p = await PanelsManager().get_panel_by_code(code=panel_code)
        if not p:
            await event.answer("❌ پنل سرویس یافت نشد!", alert=True)
            return

        # Get current user data from Marzban
        try:
            get_User = await PasarguardAPI(p.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=p.cookie
            )
            current_remaining_volume, new_remaining_volume = preview_remaining_after_renewal(p, get_User, plan)
        except Exception:
            current_remaining_volume = 0
            new_remaining_volume = gigabytes_to_bytes(float(plan.storage))

        ip_limit_text = format_ip_limit(getattr(plan, "ip_limit", 0))
        plan_name = convert_storage(
            float(plan.storage), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
        )

        # Get renewal confirmation text from database with placeholders
        confirm_text_template = await get_bot_text(
            key="renewal_final_step_text",
            default=(
                "‼️ مرحله نهایی تمدید اکانت :\n\n"
                "⚠️ لطفاً قبل از تأیید نهایی موارد زیر را بررسی کنید :\n\n"
                "#️⃣ کدسرویس: {service_code}\n"
                "📥 پلن انتخابی : {plan_name}\n"
                "📦حجم باقیمانده الان: {current_remaining_volume}\n"
                "🗳حجم باقیمانده بعد تمدید: {new_remaining_volume}\n"
                "⏰ مدت زمان بعد تمدید: {duration} روز دیگر\n"
                "🔌 محدودیت کاربر: {ip_limit}\n"
                "💸 قیمت نهایی: {price} هزار تومان\n\n"
                "⚠️ ❗️توجه:\n\n"
                "📩 بعد از تمدید - حجم باقی‌مانده از این اکانت به دوره جدید اضافه میشه و سوخت نمیشه !\n\n"
                "⏳ اما زمان انتخابی از ابتدا ریست میشه و به زمان باقیمانده فعلی اضافه نمیشه.\n\n"
                "✅ جهت تایید نهایی تمدید اکانت و کسر مبلغ از کیف پول روی دکمه تایید خرید کلیک کنید :👇"
            ),
            lang="fa",
        )

        # Replace placeholders
        confirm_text = (
            confirm_text_template.replace("{service_code}", str(ConfigID))
            .replace("{plan_name}", plan_name)
            .replace("{current_remaining_volume}", format_size(current_remaining_volume, decimal_places=0))
            .replace("{new_remaining_volume}", format_size(new_remaining_volume, decimal_places=0))
            .replace("{duration}", str(plan.duration))
            .replace("{ip_limit}", ip_limit_text)
            .replace("{price}", f"{int(plan.price):,}")
        )

        _back_confirm = await _back_to_service(event.sender_id, str(ConfigID))
        confirm_buttons = await build_ms_renew_confirm_button_rows(
            confirm_data=f"confirm_purchase_tamdid_{plan.id}",
            back_data=_back_confirm,
        )

        try:
            await event.edit(confirm_text, buttons=confirm_buttons, link_preview=False)
        except MessageNotModifiedError:
            await event.answer()
        except Exception as e:
            logger.exception("Renewal confirm edit failed for user %s: %s", event.sender_id, e)
            await event.answer("❌ خطا در نمایش صفحه تأیید تمدید.", alert=True)

    elif data.startswith("confirm_purchase_tamdid_"):
        if await get_step(event.sender_id) != "crconf_tamdid":
            await notify_session_expired(event)
            return
        parts = data.split("_")
        # New format: confirm_purchase_tamdid_{plan_id} (plan_id is unique)
        if len(parts) >= 4:
            try:
                plan_id = int(parts[3])
            except ValueError, IndexError:
                plan_id = None
        else:
            plan_id = None
        if plan_id is None:
            await event.answer("داده نامعتبر.", alert=True)
            return
        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد.", alert=True)
            return
        gig = float(plan.storage)
        panelcode = await get_data(event.sender_id, "panel")
        ConfigID = await get_data(event.sender_id, "ConfigID")
        if not ConfigID or not panelcode:
            await event.edit("خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(event.sender_id, lang))
            return
        service, serv_msg = await ServiceCRUD().get_service(code=ConfigID)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return
        if getattr(serv_msg, "is_test", False) is True:
            await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
            return
        is_sufficient, message = await check_user_balance(event.sender_id, plan.price)
        if not is_sufficient:
            await cancel_pending_for_user(event.sender_id)
            if await is_direct_pay_renew_enabled():
                volume_text = (
                    f"{convert_storage(gig, getattr(plan, 'plan_type', None), getattr(plan, 'data_limit_reset_strategy', None))}"
                    f" / {plan.duration} روز"
                )
                product_label = f"تمدید {serv_msg.username}"
                await set_data(event.sender_id, "selected_plan_id", plan_id)
                await set_data(event.sender_id, "direct_pay_config_name", serv_msg.username)
                await mark_direct_pay_ready(
                    event.sender_id,
                    kind=KIND_RENEW,
                    amount=int(plan.price),
                    product_label=product_label,
                    volume=volume_text,
                )
                message = await build_insufficient_balance_message(
                    event.sender_id,
                    int(plan.price),
                    kind=KIND_RENEW,
                    product_label=product_label,
                    volume=volume_text,
                    renew=True,
                )
                await event.edit(message, buttons=await create_direct_pay_balance_button(event.sender_id))
            else:
                await event.edit(message, buttons=await create_balance_button(event.sender_id))
        else:
            try:
                panel = await PanelsManager().get_panel_by_code(code=panelcode)
                get_User = await PasarguardAPI(panel.base_url).get_user_by_id(
                    user_id=require_panel_userid(serv_msg), token=panel.cookie
                )
                new_hajm = await apply_panel_user_renewal(panel, require_panel_userid(serv_msg), get_User, plan)

                # await ServiceCRUD().update_service(code=ConfigID, package_size=int(new_hajm))
                await ServiceCRUD().update_service(
                    code=ConfigID,
                    package_size=int(new_hajm),
                    expiration_time=day_to_timestamp(int(plan.duration)),
                    warning=0,
                    warning_time=0,
                    low_volume_notified=False,
                    expire_notified=False,
                    ip_limit=plan.ip_limit if plan and hasattr(plan, "ip_limit") else 0,
                )

                new_Amount = await update_Money(user_id=event.sender_id, Money=-int(plan.price))

                # Prepare plan name with IP limit
                plan_name = convert_storage(
                    float(gig), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
                )
                ip_limit = getattr(plan, "ip_limit", 0)
                plan_name_with_limit = f"{plan_name} [{ip_limit}] کاربره" if ip_limit and ip_limit > 0 else plan_name

                # Get renewal success text from database with placeholders
                success_text_template = await get_bot_text(
                    key="renewal_success_text",
                    default=(
                        "✅ از اعتماد شما ممنونیم !\n\n"
                        "🎉 اکانت شما با مشخصات زیر تمدید شد :\n\n"
                        "🎫 کد سرویس: {service_code}\n"
                        "📝 نام کانفیگ: {config_name}\n"
                        "📥 پلن انتخابی: {plan_name}\n"
                        "📥 حجم جدید شما: {new_volume}\n"
                        "⏳ تاریخ انقضا اکانت: {expiration_date}\n\n"
                        "💰 مبلغ {price} هزارتومان از موجودی شما کسر شد.\n\n"
                        "💵 موجودی جدید کیف‌پول شما:\n"
                        "{new_balance} هزارتومان\n\n"
                        "🌐 جهت مدیریت اکانت ها روی /myaccount کلیک کنید."
                    ),
                    lang="fa",
                )

                # Replace placeholders
                expiration_date_text = f"{plan.duration} روز دیگر"
                txt = (
                    success_text_template.replace("{service_code}", str(ConfigID))
                    .replace("{config_name}", serv_msg.username)
                    .replace("{plan_name}", plan_name_with_limit)
                    .replace("{new_volume}", format_size(new_hajm, decimal_places=0))
                    .replace("{expiration_date}", expiration_date_text)
                    .replace("{price}", f"{int(plan.price):,}")
                    .replace("{new_balance}", f"{new_Amount:,}")
                )

                log_text = (
                    f"📢 ** تمدید جدید بدون کدتخفیف**\n\n"
                    f"👤 شناسه کاربر: `{event.sender_id}`\n"
                    f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
                    f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
                    f"🎫 کد سرویس: `{ConfigID}`\n"
                    f"**🔷 اسم کانفیگ:** `{serv_msg.username}`\n"
                    f"**📥 حجم انتخابی کاربر:** {convert_storage(float(gig), getattr(plan, 'plan_type', None), getattr(plan, 'data_limit_reset_strategy', None))}\n"
                    f"**📥 حجم جدید کاربر :** `{format_size(new_hajm, decimal_places=2)}`\n"
                    f"**⏳ زمان جدید کانفیگ: {plan.duration} روز**\n"
                    f"💸 مبلغ پرداخت شده: `{int(plan.price):,}` تومان\n"
                    f"💵 موجودی جدید کاربر: `{new_Amount:,}` تومان\n."
                )
                _back_tamdid2 = await _back_to_service(event.sender_id, str(ConfigID))
                inline_service = [
                    [
                        Button.inline(f"{format_size(new_hajm, decimal_places=2)}", data="none"),
                        Button.inline("📥 حجم جدید شما :", data="none"),
                    ],
                    [Button.inline("بازگشت", data=_back_tamdid2)],
                ]
                await event.edit(txt, buttons=inline_service)

                await clear_user(event.sender_id)
                await send_log_message(LogType.OTHER, message=log_text)

            except Exception as e:
                logger.error(str(e))

    elif data.startswith("ApplyCodeTakhfifTamdid"):
        if await get_step(event.sender_id) != "crconf_tamdid":
            await notify_session_expired(event)
            return
        ConfigID = await get_data(event.sender_id, "ConfigID")
        _back_apply = await _back_to_service(event.sender_id, str(ConfigID))
        mag_id = await event.edit(
            "**🎉 کد تخفیف جادویی خود را وارد کنید!**\n💰 برای اعمال تخفیف ویژه، کد خود را همین حالا ارسال کنید! 🚀",
            parse_mode="md",
            link_preview=False,
            buttons=ReplyInlineMarkup([KeyboardInlineButtonRow([await ms_renew_back_button(_back_apply)])]),
        )
        await set_data(event.sender_id, "msg_id_takhfif", mag_id.id)
        await set_step(event.sender_id, "WhatingForCodeTakhfifTamdid")

    elif data == "Confirm_buy_tamdid":
        if await get_step(event.sender_id) != "Takhfif_confirm_purchase_tamdid":
            await notify_session_expired(event)
            return
        gig = await get_data(event.sender_id, "gig")
        new_price = await get_data(event.sender_id, "codetakhfif_newprice")
        ConfigID = await get_data(event.sender_id, "ConfigID")
        code_takhfif = await get_data(event.sender_id, "codetakhfif")
        panelcode = await get_data(event.sender_id, "panel")
        plan_id = await get_data(event.sender_id, "selected_plan_id")
        plan = await PlanManager().get_plan(plan_id)

        # Check if information exists
        if gig is None or panelcode is None or plan is None or new_price is None or code_takhfif is None:
            await event.edit("خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(event.sender_id, lang))
            return
        service, serv_msg = await ServiceCRUD().get_service(code=ConfigID)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return

        # Convert new_price to int (may be string or float)
        try:
            new_price = int(float(new_price))
        except ValueError, TypeError:
            new_price = plan.price

        is_sufficient, message = await check_user_balance(event.sender_id, new_price)
        if not is_sufficient:
            await cancel_pending_for_user(event.sender_id)
            if await is_direct_pay_renew_enabled():
                volume_text = (
                    f"{convert_storage(float(gig), getattr(plan, 'plan_type', None), getattr(plan, 'data_limit_reset_strategy', None))}"
                    f" / {plan.duration} روز"
                )
                product_label = f"تمدید {serv_msg.username}"
                await set_data(event.sender_id, "selected_plan_id", plan_id)
                await set_data(event.sender_id, "direct_pay_config_name", serv_msg.username)
                await mark_direct_pay_ready(
                    event.sender_id,
                    kind=KIND_RENEW,
                    amount=int(new_price),
                    product_label=product_label,
                    volume=volume_text,
                )
                message = await build_insufficient_balance_message(
                    event.sender_id,
                    int(new_price),
                    kind=KIND_RENEW,
                    product_label=product_label,
                    volume=volume_text,
                    renew=True,
                )
                await event.edit(message, buttons=await create_direct_pay_balance_button(event.sender_id))
            else:
                await event.edit(message, buttons=await create_balance_button(event.sender_id))

        else:
            try:
                status, _res = await DiscountCodeManager().validate_discount_code(
                    code=code_takhfif, user_id=event.sender_id
                )
                if status:
                    panel = await PanelsManager().get_panel_by_code(code=panelcode)
                    get_User = await PasarguardAPI(panel.base_url).get_user_by_id(
                        user_id=require_panel_userid(serv_msg), token=panel.cookie
                    )
                    new_hajm = await apply_panel_user_renewal(panel, require_panel_userid(serv_msg), get_User, plan)
                    panel = await PanelsManager().get_panel_by_code(code=panelcode)
                    # await ServiceCRUD().update_service(code=ConfigID, package_size=int(new_hajm))
                    await ServiceCRUD().update_service(
                        code=ConfigID,
                        package_size=int(new_hajm),
                        expiration_time=day_to_timestamp(int(plan.duration)),
                        warning=0,
                        warning_time=0,
                        low_volume_notified=False,
                        expire_notified=False,
                        ip_limit=plan.ip_limit if plan and hasattr(plan, "ip_limit") else 0,
                    )

                    new_Amount = await update_Money(user_id=event.sender_id, Money=-int(new_price))

                    # Prepare plan name with IP limit
                    plan_name = convert_storage(
                        float(gig),
                        getattr(plan, "plan_type", None),
                        getattr(plan, "data_limit_reset_strategy", None),
                    )
                    ip_limit = getattr(plan, "ip_limit", 0)
                    if ip_limit and ip_limit > 0:
                        plan_name_with_limit = f"{plan_name} [{ip_limit}] کاربره"
                    else:
                        plan_name_with_limit = plan_name

                    # Get renewal success text from database with placeholders
                    success_text_template = await get_bot_text(
                        key="renewal_success_text",
                        default=(
                            "✅ از اعتماد شما ممنونیم !\n\n"
                            "🎉 اکانت شما با مشخصات زیر تمدید شد :\n\n"
                            "🎫 کد سرویس: {service_code}\n"
                            "📝 نام کانفیگ: {config_name}\n"
                            "📥 پلن انتخابی: {plan_name}\n"
                            "📥 حجم جدید شما: {new_volume}\n"
                            "⏳ تاریخ انقضا اکانت: {expiration_date}\n\n"
                            "💰 مبلغ {price} هزارتومان از موجودی شما کسر شد.\n\n"
                            "💵 موجودی جدید کیف‌پول شما:\n"
                            "{new_balance} هزارتومان\n\n"
                            "🌐 جهت مدیریت اکانت ها روی /myaccount کلیک کنید."
                        ),
                        lang="fa",
                    )

                    # Replace placeholders
                    expiration_date_text = f"{plan.duration} روز دیگر"
                    txt = (
                        success_text_template.replace("{service_code}", str(ConfigID))
                        .replace("{config_name}", serv_msg.username)
                        .replace("{plan_name}", plan_name_with_limit)
                        .replace("{new_volume}", format_size(new_hajm, decimal_places=0))
                        .replace("{expiration_date}", expiration_date_text)
                        .replace("{price}", f"{int(new_price):,}")
                        .replace("{new_balance}", f"{new_Amount:,}")
                    )

                    log_text = (
                        f"📢 ** تمدید جدید با کدتخفیف**\n\n"
                        f"👤 شناسه کاربر: `{event.sender_id}`\n"
                        f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
                        f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
                        f"🎫 کد سرویس: `{ConfigID}`\n"
                        f"🎟 **کدتخفیف استفاده شده:** `{code_takhfif}`\n"
                        f"**📥 حجم انتخابی کاربر:** {convert_storage(float(gig), getattr(plan, 'plan_type', None), getattr(plan, 'data_limit_reset_strategy', None))}\n"
                        f"**📥 حجم جدید کاربر :** `{format_size(new_hajm, decimal_places=2)}`\n"
                        f"**⏳ زمان جدید کانفیگ: {plan.duration} روز**\n"
                        f"💸 مبلغ بدون تخفیف: `{int(plan.price):,}` تومان\n"
                        f"💸 مبلغ پرداخت شده: `{int(new_price):,}` تومان\n"
                        f"💸 مقدارتخفیف  : `{int(float(plan.price) - float(new_price)):,}` تومان\n"
                        f"💵 موجودی جدید کاربر: `{new_Amount:,}` تومان\n."
                    )

                    _back_tamdid3 = await _back_to_service(event.sender_id, str(ConfigID))
                    inline_service = [
                        [
                            Button.inline(f"{format_size(new_hajm, decimal_places=2)}", data="none"),
                            Button.inline("📥 حجم جدید شما :", data="none"),
                        ],
                        [Button.inline("بازگشت", data=_back_tamdid3)],
                    ]
                    await event.edit(txt, buttons=inline_service)
                    await send_log_message(LogType.OTHER, message=log_text)
                    await clear_user(event.sender_id)
                    await DiscountCodeManager().update_discount_usage(code=code_takhfif)

            except Exception as e:
                logger.error(str(e))

    elif data.startswith("PrevService") or data.startswith("NextService"):
        if await get_step(event.sender_id) != "SelectService":
            await notify_session_expired(event)
            return
        parts = data.split(":")  # Split data based on ':'

        if len(parts) == 2:  # Ensure we have two parts
            direction = parts[0]
            current_page = int(parts[1])

            if direction == "PrevService":
                current_page -= 1
                await UserCRUD().update_user(user_id=event.sender_id, page=current_page)
            elif direction == "NextService":
                current_page += 1
                await UserCRUD().update_user(user_id=event.sender_id, page=current_page)

            current_page = await UserCRUD().read_user(event.sender_id)

            await display_user_services(event.sender_id, current_page.page, edit_message=True, original_event=event)
        else:
            await event.respond("داده نامعتبر است.")  # Error message if no match

    # Handle callback query for "back" button
    # elif await get_step(event.sender_id) == 'SelectService' or await get_step(event.sender_id) == 'LinkChanged' or await get_step(event.sender_id) == 'ChangeProtocol_Select'or await get_step(event.sender_id) == 'ChangeLocation_Finish'  and data.startswith("service_info:"):

    elif data.startswith("othersSubLinks:"):
        service_code = data.split(":")[1]
        await display_subscription_links(event, service_code, 1)
    elif data.startswith("NextSubLinks:") or data.startswith("PrevSubLinks:"):
        parts = data.split(":")
        if len(parts) == 3:
            direction = parts[0]
            service_code = parts[1]
            current_page = int(parts[2])
            if direction == "NextSubLinks":
                current_page += 1
            else:
                current_page -= 1
            await display_subscription_links(event, service_code, current_page)
        else:
            await event.answer("داده نامعتبر است!", alert=True)
    elif data.startswith("showSubLink:"):
        parts = data.split(":")
        if len(parts) == 3:
            service_code = parts[1]
            index = int(parts[2])
            try:
                service, serv_msg = await ServiceCRUD().get_service(code=service_code)
                if not service:
                    await event.answer("❌ سرویس یافت نشد!", alert=True)
                    return

                info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
                if not info_panel:
                    await event.answer("❌ پنل یافت نشد!", alert=True)
                    return

                links = await fetch_user_config_links(info_panel, require_panel_userid(serv_msg))

                if 0 <= index < len(links):
                    page = index // SUB_LINKS_PAGE_LIMIT + 1
                    await display_subscription_links(event, service_code, page, selected_index=index)
                else:
                    await event.answer("❌ لینک مورد نظر وجود ندارد!", alert=True)
            except Exception as e:
                await event.edit("❌ خطایی رخ داد هنگام دریافت لینک")
                logger.error(f"❌ خطایی رخ داد هنگام دریافت لینک:\n{e!s}")
        else:
            await event.answer("داده نامعتبر است!", alert=True)
    elif data.startswith("get_single_links:"):
        service_code = data.split(":")[1]
        try:
            service, serv_msg = await ServiceCRUD().get_service(code=service_code)
            if not service:
                await event.answer("❌ سرویس یافت نشد!", alert=True)
                return

            info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
            if not info_panel:
                await event.answer("❌ پنل یافت نشد!", alert=True)
                return

            await event.answer("⏳ در حال دریافت لینک‌های کانفیگ...")

            links = await fetch_user_config_links(info_panel, require_panel_userid(serv_msg))

            if not links:
                await event.respond("❌ هیچ لینکی برای این سرویس پیدا نشد.")
                return

            total = len(links)
            links_text = "\n".join(links)

            if len(links_text) < 4000:
                message = f"✅ تعداد کانفیگ‌ها: {total} عدد\n\n```{links_text}```"
                await event.respond(message)
            else:
                filename = f"{service_code}_links.txt"
                await asyncio.to_thread(lambda: Path(filename).write_text(links_text, encoding="utf-8"))

                await event.respond(
                    f"✅ تعداد لینک‌ها زیاد است، فایل زیر را بررسی کن\n📦 تعداد کانفیگ‌ها: {total} عدد", file=filename
                )
                os.remove(filename)

        except Exception as e:
            await event.respond("❌ خطایی رخ داد هنگام دریافت لینک‌ها")
            logger.error(f"❌ خطایی رخ داد هنگام دریافت لینک‌ها:\n{e!s}")

    elif data.startswith("get_xhttp_links:"):
        service_code = data.split(":")[1]
        try:
            service, serv_msg = await ServiceCRUD().get_service(code=service_code)
            if not service:
                await event.answer("❌ سرویس یافت نشد!", alert=True)
                return

            info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
            if not info_panel:
                await event.answer("❌ پنل یافت نشد!", alert=True)
                return

            await event.answer("⏳ در حال دریافت لینک‌های XHTTP...")

            user = await PasarguardAPI(info_panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=info_panel.cookie
            )
            links = user.links if user and user.links else []

            xhttp_links = [link for link in links if "type=xhttp" in link]

            if not xhttp_links:
                await event.respond("❌ هیچ لینک XHTTP برای این سرویس پیدا نشد.")
                return

            total = len(xhttp_links)
            links_text = "\n".join(xhttp_links)

            if len(links_text) < 4000:
                message = f"✅ تعداد کانفیگ‌های XHTTP: {total} عدد\n\n```{links_text}```"
                await event.respond(message)
            else:
                filename = f"{service_code}_xhttp_links.txt"
                await asyncio.to_thread(lambda: Path(filename).write_text(links_text, encoding="utf-8"))

                await event.respond(
                    f"✅ تعداد لینک‌های XHTTP زیاد است، فایل زیر را بررسی کن\n📦 تعداد کانفیگ‌ها: {total} عدد",
                    file=filename,
                )
                os.remove(filename)

        except Exception as e:
            await event.respond("❌ خطایی رخ داد هنگام دریافت لینک‌های XHTTP")
            logger.error(f"❌ خطا در دریافت لینک‌های XHTTP:\n{e!s}")

    elif data.startswith("showClients:"):
        service_code = data.split(":")[1]
        await display_subscription_clients(event, service_code)

    elif data.startswith("UsageChart:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        service_code = parts[1]
        days = max(7, min(int(parts[2]), 30))
        page = max(0, int(parts[3]))
        await display_usage_chart(event, service_code, days=days, page=page)

    elif data.startswith("UsageChartDay:"):
        parts = data.split(":")
        if len(parts) < 3:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        service_code = parts[1]
        day_iso = parts[2]
        days = int(parts[3]) if len(parts) > 3 else 7
        page = int(parts[4]) if len(parts) > 4 else 0
        await display_usage_chart_day(event, service_code, day_iso, days=days, page=page)

    elif data.startswith("service_info:"):
        service_code = data.split(":")[1]
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return

        InfoPanel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if InfoPanel is None:
            await event.answer("پنل یافت نشد!", alert=True)
            return
        try:
            if serv_msg.id != event.sender_id and event.sender_id not in ADMIN_ID:
                await event.answer("این کانفیگ برای شما نیست پس نمیتوانید اطلاعات اون رو مشاهده کنید", alert=True)
                return
            User: UserResponse = await PasarguardAPI(InfoPanel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=InfoPanel.cookie
            )
            service_info_text, primary_subscription_url = await build_service_info_message_text(
                serv_msg, InfoPanel, User
            )
            await set_step(event.sender_id, f"ToService:{serv_msg.code}")
            settings = await SettingsManager().get_settings()
            inline_service = await create_inline_service_buttons(
                services=serv_msg,
                panel=InfoPanel,
                settings=settings,
                link=f"{primary_subscription_url}",
                status=User.status,
            )
            # Generate QR code URL
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
                await event.edit("خطا: کاربر مورد نظر پیدا نشد. لطفاً نام کاربری را بررسی کنید.")
                logger.error("خطا: کاربر مورد نظر پیدا نشد. لطفاً نام کاربری را بررسی کنید.")
            else:
                await event.edit("خطا در دریافت اطلاعات کاربر")
                logger.error(f"خطا در دریافت اطلاعات کاربر: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            await event.edit("خطای غیرمنتظره")
            logger.error(f"خطای غیرمنتظره: {e!s}")

    elif data in ("BackToServiceList", "BackToServiceListFromCredential"):
        current_page = await UserCRUD().read_user(event.sender_id)
        await set_step(event.sender_id, "SelectService")
        await display_user_services(
            event.sender_id, current_page=current_page.page, edit_message=True, original_event=event
        )

    elif data.startswith("DeleteService:"):
        service_code = data.split(":")[1]
        _back_del = await _back_to_service(event.sender_id, service_code)
        warn_text = "⚠️ حذف این سرویس غیرقابل بازگشت است. آیا مطمئن هستید؟"
        buttons = [
            [Button.inline("✅ بله", data=f"ConfirmDelete:{service_code}")],
            [Button.inline("🔙 بازگشت", data=_back_del)],
        ]
        await event.edit(warn_text, buttons=buttons)
        await set_step(event.sender_id, f"DeleteConfirm:{service_code}")

    elif data.startswith("ConfirmDelete:"):
        if not (await get_step(event.sender_id) or "").startswith("DeleteConfirm:"):
            await notify_session_expired(event)
            return
        service_code = data.split(":")[1]
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if panel is None:
            await ServiceCRUD().delete_service(code=service_code)
            await event.edit("سرویس از دیتابیس حذف شد.", buttons=[[Button.inline("بازگشت", data="BackToServiceList")]])

            await send_log_message(
                LogType.OTHER, message=f"کانفیگ [{serv_msg.username}] توسط [{event.sender_id}]  از دیتابیس پاک شد"
            )
            await set_step(event.sender_id, "ToService")
            return
        user_info = await PasarguardAPI(panel.base_url).get_user_by_id(
            user_id=require_panel_userid(serv_msg), token=panel.cookie
        )
        if user_info.status not in ["disabled", "expired", "limited"]:
            _back_del2 = await _back_to_service(event.sender_id, service_code)
            await event.edit(
                "این سرویس هنوز فعال است و امکان حذف آن وجود ندارد.",
                buttons=[[Button.inline("بازگشت", data=_back_del2)]],
            )
            await set_step(event.sender_id, f"ToService:{service_code}")
            return
        await PasarguardAPI(panel.base_url).remove_user_by_id(
            user_id=require_panel_userid(serv_msg), token=panel.cookie
        )
        await ServiceCRUD().delete_service(code=service_code)
        await event.edit(
            "سرویس با موفقیت حذف شد.",
            buttons=[[Button.inline("بازگشت", data="BackToServiceList")]],
        )
        await send_log_message(LogType.OTHER, message=f"کانفیگ [{serv_msg.username}] توسط [{event.sender_id}] حذف شد")
        await set_step(event.sender_id, "ToService")

    elif data.startswith("ChangeLink:"):
        data = event.data.decode("utf-8")
        _, panel_code, service_code = data.split(":")

        InfoPanel = await PanelsManager().get_panel_by_code(code=panel_code)
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service or await _deny_unless_service_owner_or_admin(event, serv_msg):
            return
        panel_userid = require_panel_userid(serv_msg)
        revoke = await PasarguardAPI(InfoPanel.base_url).modify_user_by_id(
            user_id=panel_userid,
            user=UserModify(
                proxy_settings=ProxySettings(),
            ),
            token=InfoPanel.cookie,
        )

        service_info_text = "**🔗 لینک تمام کانفیگ های شما تغییر کرد لطفا ساب خودتون رو یکبار اپدیت کنید**"
        back_data = await _back_to_service(event.sender_id, service_code)
        inline_service = [
            [Button.inline("بازگشت", data=back_data)],
        ]
        await event.edit(service_info_text, buttons=inline_service)
        await set_step(event.sender_id, "LinkChanged")
        await event.answer(message="**🔗 لینک اتصال شما با موفقیت تغییر کرد.**", alert=False)
        subscription_url_log = revoke.subscription_url
        if subscription_url_log and not subscription_url_log.startswith("http"):
            subscription_url_log = f"{InfoPanel.base_url}{subscription_url_log}"
        log_text = (
            f"🔗 **تغییر لینک اتصال**\n\n"
            f"👻 شناسه کاربر: `{event.sender_id}`\n"
            f"📅 تاریخ تغییر (میلادی): `{Time_Date()['mf']}`\n"
            f"📅 تاریخ تغییر (شمسی): `{Time_Date()['jf']}`\n"
            f"🔖 کد پنل: `{panel_code}`\n"
            f"🎫 کد سرویس: `{service_code}`\n"
            f"🔗 لینک جدید: `{subscription_url_log}`"
        )

        await send_log_message(LogType.OTHER, message=log_text)

    elif data.startswith("ChangeSub:"):
        data = event.data.decode("utf-8")
        _, panel_code, service_code = data.split(":")
        InfoPanel = await PanelsManager().get_panel_by_code(code=panel_code)
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service or await _deny_unless_service_owner_or_admin(event, serv_msg):
            return
        revoke = await PasarguardAPI(InfoPanel.base_url).revoke_user_subscription(
            username=serv_msg.username, token=InfoPanel.cookie
        )
        subscription_url = revoke.subscription_url
        if subscription_url and not subscription_url.startswith("http"):
            subscription_url = f"{InfoPanel.base_url}{subscription_url}"
        subscription_links_text, _primary_subscription_url = format_subscription_links_for_message(
            InfoPanel,
            subscription_url,
            main_label="🔗 لینک جدید شما",
            tunnel_label="🌐 لینک تانل جدید شما",
        )
        service_info_text = (
            f"**🔗 لینک ساب وتمام کانفیگ های شما با موفقیت تغییر کرد.**\n\n{subscription_links_text}\n\n."
        )
        back_data = await _back_to_service(event.sender_id, service_code)
        inline_service = [
            [Button.inline("بازگشت", data=back_data)],
        ]
        await event.edit(service_info_text, buttons=inline_service)
        await set_step(event.sender_id, "LinkSubChanged")
        await event.answer(message="**🔗 لینک ساب شما با موفقیت تغییر کرد.**", alert=False)
        subscription_url_log = revoke.subscription_url
        if subscription_url_log and not subscription_url_log.startswith("http"):
            subscription_url_log = f"{InfoPanel.base_url}{subscription_url_log}"
        log_text = (
            f"🔗 **تغییر لینک ساب**\n\n"
            f"👻 شناسه کاربر: `{event.sender_id}`\n"
            f"📅 تاریخ تغییر (میلادی): `{Time_Date()['mf']}`\n"
            f"📅 تاریخ تغییر (شمسی): `{Time_Date()['jf']}`\n"
            f"🔖 کد پنل: `{panel_code}`\n"
            f"🎫 کد سرویس: `{service_code}`\n"
            f"🔗 لینک جدید: `{subscription_url_log}`"
        )

        await send_log_message(LogType.OTHER, message=log_text)

    elif data.startswith("KharidSize:"):
        data = event.data.decode("utf-8")
        _, service_code = data.split(":")
        _step = (await get_step(event.sender_id)) or ""
        if _step.startswith("ToServiceAdmin:"):
            await set_data(event.sender_id, "from_admin", "1")

        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if service and getattr(serv_msg, "is_test", False) is True:
            await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
            return
        await cancel_pending_for_user(event.sender_id)
        if service and serv_msg.package_size:
            panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
            if panel:
                plan = await PlanManager().get_plan_by_volume_for_display(
                    gb=serv_msg.package_size / (1024**3),
                    panel_code=panel.code,
                )
                if plan and hasattr(plan, "plan_type") and plan.plan_type in ["fair_usage", "fair"]:
                    back_data = await _back_to_service(event.sender_id, service_code)
                    await event.edit(
                        "❌ امکان خرید حجم اضافی برای پلن‌های مصرف منصفانه وجود ندارد.\n"
                        "در پلن‌های مصرف منصفانه، حجم به صورت خودکار ریست می‌شود.",
                        buttons=[[Button.inline("بازگشت", data=back_data)]],
                    )
                    return

        back_data = await _back_to_service(event.sender_id, service_code)
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel) if serv_msg else None
        if not panel or not panel_has_volume_plans(panel):
            await event.answer("❌ در حال حاضر پلن حجم اضافه‌ای برای این پنل تعریف نشده است.", alert=True)
            return
        volume_plans = panel_volume_plans(panel)
        kharideSize_txt = build_volume_upgrade_tariff_text(volume_plans)
        inline_service = build_volume_upgrade_select_buttons(panel, service_code, back_data)
        await event.edit(kharideSize_txt, buttons=inline_service)
        await set_step(event.sender_id, "KharidSize_Select")

    elif data.startswith("upgSize@"):
        if await get_step(event.sender_id) != "KharidSize_Select":
            await notify_session_expired(event)
            return
        parts = data.split("@")
        service_code = parts[1]
        plan_id = int(parts[2])
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return
        if getattr(serv_msg, "is_test", False) is True:
            await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
            return
        info_panel = await PanelsManager().get_panel_by_code(serv_msg.in_panel)
        plan = get_panel_volume_plan(info_panel, plan_id) if info_panel else None
        if not plan:
            await event.answer("❌ پلن حجم انتخاب‌شده معتبر نیست.", alert=True)
            return
        size = plan["storage_gb"]
        price = int(plan["price"])
        is_sufficient, message = await check_user_balance(event.sender_id, price)
        back_data = await _back_to_service(event.sender_id, service_code)
        if not is_sufficient:
            await cancel_pending_for_user(event.sender_id)
            balance_btn_text = await get_button_text("bt.menu_add_balance", "💰 افزایش موجودی")
            await event.edit(
                message,
                buttons=[
                    [
                        Button.inline(balance_btn_text, data="back_to_balance"),
                        Button.inline("🔙 بازگشت", data=back_data),
                    ]
                ],
            )
        else:
            _, panel_id = await ServiceCRUD().get_service(code=service_code)
            InfoPanel = await PanelsManager().get_panel_by_code(panel_id.in_panel)
            get_User: UserResponse = await PasarguardAPI(InfoPanel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=InfoPanel.cookie
            )
            old_limit = int(get_User.data_limit or 0)
            new_hajm = old_limit + gigabytes_to_bytes(float(size))

            addhajm = UserModify(data_limit=(int(new_hajm)))

            await PasarguardAPI(InfoPanel.base_url).modify_user_by_id(
                user_id=require_panel_userid(serv_msg), user=addhajm, token=InfoPanel.cookie
            )

            new_Amount = await update_Money(user_id=event.sender_id, Money=-int(price))
            await ServiceCRUD().update_service(
                code=service_code,
                package_size=int(new_hajm),
                low_volume_notified=False,
            )
            await event.edit(
                "✅ **افزایش حجم با موفقیت انجام شد**\n\n"
                f"**🔷 نام کانفیگ:** `{serv_msg.username}`\n"
                f"**➕ حجم اضافه‌شده:** `{size}` گیگ\n"
                f"**📦 حجم کل جدید:** `{format_size(new_hajm, decimal_places=2)}`\n\n"
                f"**💵 مبلغ کسر شده:** `{int(price):,}` تومان\n"
                f"**💰 موجودی جدید:** `{int(new_Amount):,}` تومان",
                buttons=[[Button.inline("بازگشت", data=back_data)]],
            )
            log_text = (
                f"🔼 **خرید حجم**\n\n"
                f"👻 شناسه کاربر: `{event.sender_id}`\n"
                f"🎫 کد سرویس: `{service_code}`\n"
                f"**🔷 اسم کانفیگ:** `{serv_msg.username}`\n"
                f"📦 حجم: `{size}`\n"
                f"📦 حجم جدید: `{format_size(new_hajm, decimal_places=2)}`\n"
                f"📅 تاریخ ارتقاء (میلادی): `{Time_Date()['mf']}`\n"
                f"📅 تاریخ ارتقاء (شمسی): `{Time_Date()['jf']}`\n"
                f"💵 مبلغ کسر شده: `{int(price):,}` **تومان**\n"
                f"💰 موجودی جدید: `{new_Amount:,}` **تومان**"
            )

            await send_log_message(LogType.OTHER, message=log_text)

    elif data.startswith("KharidZaman:"):
        data = event.data.decode("utf-8")
        _, service_code = data.split(":")
        _step = (await get_step(event.sender_id)) or ""
        if _step.startswith("ToServiceAdmin:"):
            await set_data(event.sender_id, "from_admin", "1")

        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if service and getattr(serv_msg, "is_test", False) is True:
            await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
            return
        await cancel_pending_for_user(event.sender_id)
        back_data = await _back_to_service(event.sender_id, service_code)
        panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel) if serv_msg else None
        if not panel or not panel_has_time_plans(panel):
            await event.answer("❌ در حال حاضر پلن زمان اضافه‌ای برای این پنل تعریف نشده است.", alert=True)
            return
        time_plans = panel_time_plans(panel)
        KharidZaman_txt = build_time_upgrade_tariff_text(time_plans)
        inline_service = build_time_upgrade_select_buttons(panel, service_code, back_data)
        await event.edit(KharidZaman_txt, buttons=inline_service)
        await set_step(event.sender_id, "KharidZaman_Select")

    elif data.startswith("upgTime@"):
        if await get_step(event.sender_id) != "KharidZaman_Select":
            await notify_session_expired(event)
            return
        parts = data.split("@")
        service_code = parts[1]
        plan_id = int(parts[2])
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("سرویس یافت نشد!", alert=True)
            return
        if getattr(serv_msg, "is_test", False) is True:
            await event.answer("سرویس‌های تست قابل تمدید یا ارتقا نیستند.", alert=True)
            return
        info_panel = await PanelsManager().get_panel_by_code(serv_msg.in_panel)
        plan = get_panel_time_plan(info_panel, plan_id) if info_panel else None
        if not plan:
            await event.answer("❌ پلن زمان انتخاب‌شده معتبر نیست.", alert=True)
            return
        day_time = plan["duration_days"]
        price = int(plan["price"])
        is_sufficient, message = await check_user_balance(event.sender_id, price)
        back_data = await _back_to_service(event.sender_id, service_code)
        if not is_sufficient:
            await cancel_pending_for_user(event.sender_id)
            balance_btn_text = await get_button_text("bt.menu_add_balance", "💰 افزایش موجودی")
            await event.edit(
                message,
                buttons=[
                    [
                        Button.inline(balance_btn_text, data="back_to_balance"),
                        Button.inline("🔙 بازگشت", data=back_data),
                    ]
                ],
            )
        else:
            _, panel_id = await ServiceCRUD().get_service(code=service_code)
            InfoPanel = await PanelsManager().get_panel_by_code(panel_id.in_panel)
            get_User: UserResponse = await PasarguardAPI(InfoPanel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=InfoPanel.cookie
            )
            old_expire = get_User.expire
            new_time = old_expire + timedelta(days=int(day_time))

            addtime = UserModify(expire=new_time)

            await PasarguardAPI(InfoPanel.base_url).modify_user_by_id(
                user_id=require_panel_userid(serv_msg), user=addtime, token=InfoPanel.cookie
            )

            new_Amount = await update_Money(user_id=event.sender_id, Money=-int(price))
            await ServiceCRUD().update_service(
                code=service_code,
                expiration_time=new_time.timestamp(),
                warning=0,
                warning_time=0,
                expire_notified=False,
            )
            await event.edit(
                "✅ **افزایش زمان با موفقیت انجام شد**\n\n"
                f"**🔷 نام کانفیگ:** `{serv_msg.username}`\n"
                f"**➕ زمان اضافه‌شده:** `{day_time}` روز\n"
                f"**📅 انقضای جدید:** `{timestamp_to_persian_expiry(new_time.timestamp())}`\n\n"
                f"**💵 مبلغ کسر شده:** `{int(price):,}` تومان\n"
                f"**💰 موجودی جدید:** `{int(new_Amount):,}` تومان",
                buttons=[[Button.inline("بازگشت", data=back_data)]],
            )
            log_text = (
                f"⏳ **افزایش مدت زمان اعتبار**\n\n"
                f"👻 شناسه کاربر: `{event.sender_id}`\n"
                f"🎫 کد سرویس: `{service_code}`\n"
                f"**🔷 اسم کانفیگ:** `{serv_msg.username}`\n"
                f"📅 مدت زمان خریداری شده: `{day_time}` روز\n"
                f"📅 مدت زمان جدید: `{timestamp_to_persian_expiry(new_time)}`\n"
                f"📅 تاریخ افزایش (میلادی): `{Time_Date()['mf']}`\n"
                f"📅 تاریخ افزایش (شمسی): `{Time_Date()['jf']}`\n"
                f"💵 مبلغ کسر شده: `{int(price):,}` **تومان**\n"
                f"💰 موجودی جدید: `{new_Amount:,}` **تومان**"
            )

            await send_log_message(LogType.OTHER, message=log_text)

    elif data.startswith("getQrcode:"):
        code = event.data.decode("utf-8").replace("getQrcode:", "")
        _stats, SERVICE = await ServiceCRUD().get_service(code=code)
        if not _stats or await _deny_unless_service_owner_or_admin(event, SERVICE):
            return
        PANEL = await PanelsManager().get_panel_by_code(code=SERVICE.in_panel)
        Get_user = await PasarguardAPI(PANEL.base_url).get_user_by_id(
            user_id=require_panel_userid(SERVICE), token=PANEL.cookie
        )
        subscription_url = (
            Get_user.subscription_url
            if Get_user.subscription_url.startswith("http")
            else f"{PANEL.base_url}{Get_user.subscription_url}"
        )
        tunnel_subscription_url = build_tunnel_subscription_url(subscription_url, PANEL.tunnel_url)
        _, _, primary_subscription_url = resolve_subscription_display_urls(
            PANEL, subscription_url, tunnel_subscription_url
        )
        qr_file = create_qr_code(text=f"{primary_subscription_url}", filename=f"{code}.png")
        await event.respond(
            message=f"لینک اتصال شما به همرا کیو ار کد:\n\n`{primary_subscription_url}`\n.",
            file=qr_file,
        )

    elif data.startswith("TransferConfig:"):
        code = event.data.decode("utf-8").replace("TransferConfig:", "")
        _stats, SERVICE = await ServiceCRUD().get_service(code=code)
        if not _stats or await _deny_unless_service_owner_or_admin(event, SERVICE):
            return
        # _stats, SERVICE = await ServiceCRUD().get_service(code=code)
        # PANEL = await PanelsManager().get_panel_by_code(code=SERVICE.in_panel)
        # Get_user = await PasarguardAPI(PANEL.base_url).get_user_by_username(username=f"User{code}", token=PANEL.cookie)
        # create_qr_code(text=f"{PANEL.base_url}{Get_user.subscription_url}", file_path=f"{code}.png")

        _back_transfer = await _back_to_service(event.sender_id, code)
        await event.edit(
            text=f"برای انتقال کانفیگ با کد [{code}] برای شخص دیگری لطفا شناسه عددی کاربر رو ارسال کنید",
            buttons=[[Button.inline("🔙 برگشت", data=_back_transfer)]],
        )
        await set_step(user_id=event.sender_id, step="whating_send_TransferConfig")
        await set_data(event.sender_id, "TransferConfig", code)

    raise events.StopPropagation


def register(client):
    client.add_event_handler(service_callback_handler, events.CallbackQuery(func=service_callback_filter))

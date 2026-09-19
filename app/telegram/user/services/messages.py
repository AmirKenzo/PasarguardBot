"""Message handlers for user service management flow."""

from __future__ import annotations

from pasarguard import PasarguardAPI, UserModify
from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.services.billing.renewal import (
    require_panel_userid,
)
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, delete_data_many, get_data, get_step, set_data, set_step
from app.telegram.user.services import helpers, states
from app.telegram.user.services.search import validate_service_search_query
from app.utils.formatting.conversions import convert_storage, gigabytes_to_bytes
from app.utils.formatting.traffic import format_ip_limit, format_size
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID

logger = get_logger(__name__)


@bot_is_offline
async def my_services_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    await delete_data_many(
        user_id,
        (
            states.SERVICE_SEARCH_QUERY_KEY,
            states.SERVICE_SEARCH_PAGE_KEY,
            states.SERVICE_SEARCH_RETURN_KEY,
        ),
    )
    await set_step(user_id=user_id, step="SelectService")
    await UserCRUD().update_user(user_id=user_id, page=1)
    current_page = await UserCRUD().read_user(user_id)
    await helpers.display_user_services(user_id, current_page=current_page.page, original_event=event)
    raise events.StopPropagation


# Service management callbacks — guards in helpers/callback_guards.py.


@bot_is_offline
async def service_message_handler(event: Message):
    msg = event.message.message or event.message.text or ""
    info = await UserCRUD().read_user(event.sender_id)
    lang = info.language if info and info.language else states.BOT_LANGUAGE
    step = await get_step(event.sender_id)

    if step == states.SERVICE_SEARCH_INPUT_STEP:
        query, error = validate_service_search_query(msg)
        if error:
            await event.respond(
                error,
                buttons=[[Button.inline("📋 بازگشت به همه سرویس‌ها", data=states.SERVICE_SEARCH_CLEAR_CALLBACK)]],
            )
            raise events.StopPropagation

        await set_data(event.sender_id, states.SERVICE_SEARCH_QUERY_KEY, query)
        await set_step(event.sender_id, states.SERVICE_SEARCH_RESULTS_STEP)
        await helpers.display_user_service_search_results(event.sender_id, query, page=1)
        raise events.StopPropagation

    if step == "WhatingForCodeTakhfifTamdid":
        status, res = await DiscountCodeManager().validate_discount_code(code=msg, user_id=event.sender_id)
        msg_id_takhfif = await get_data(event.sender_id, "msg_id_takhfif")
        await event.client.delete_messages(event.chat_id, msg_id_takhfif)
        if not status:
            await event.respond(f"{res}", buttons=await bhome_buttons(event.sender_id, lang))
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "home")
            raise events.StopPropagation

        ConfigID = await get_data(event.sender_id, "ConfigID")
        panelCode = await get_data(event.sender_id, "panel")
        Hajm = await get_data(event.sender_id, "gig")
        panel = await PanelsManager().get_panel_by_code(code=panelCode)
        plan_id = await get_data(event.sender_id, "selected_plan_id")
        if plan_id:
            plan = await PlanManager().get_plan(plan_id)
        else:
            plan = await PlanManager().get_plan_by_volume_for_display(gb=float(Hajm), panel_code=panelCode)
        deduction = plan.price * (res.discount_percentage / 100)
        new_amount = int(plan.price - deduction)

        service, serv_msg = await ServiceCRUD().get_service(code=ConfigID)
        if not service:
            await event.respond("❌ سرویس یافت نشد!", buttons=await bhome_buttons(event.sender_id, lang))
            return

        try:
            from app.services.billing.renewal import preview_remaining_after_renewal

            get_User = await PasarguardAPI(panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=panel.cookie
            )
            current_remaining_volume, new_remaining_volume = preview_remaining_after_renewal(panel, get_User, plan)
        except Exception:
            current_remaining_volume = 0
            new_remaining_volume = gigabytes_to_bytes(float(Hajm))

        plan_name = convert_storage(
            float(Hajm), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
        )
        ip_limit = getattr(plan, "ip_limit", 0)
        ip_limit_text = format_ip_limit(ip_limit)
        plan_name_with_limit = f"{plan_name} {ip_limit} کاربره" if ip_limit and ip_limit > 0 else plan_name

        confirm_text_template = await get_bot_text(
            key="renewal_discount_confirm_text",
            default=(
                "‼️ مرحله نهایی تمدید اکانت :\n\n"
                "⚠️ لطفاً قبل از تأیید نهایی موارد زیر را بررسی کنید :\n\n"
                "#️⃣ کدسرویس: {service_code}\n"
                "📥 پلن انتخابی : {plan_name}\n"
                "📦حجم باقیمانده الان: {current_remaining_volume}\n"
                "🗳حجم باقیمانده بعد تمدید: {new_remaining_volume}\n"
                "⏰ مدت زمان بعد تمدید: {duration} روز دیگر\n"
                "🔌 محدودیت کاربر: {ip_limit}\n"
                "🎁 کد تخفیف: {discount_code}\n"
                "💰 مبلغ کسر شده: {discount_amount} هزار تومان\n"
                "💸 قیمت قبل از تخفیف: {original_price} هزار تومان\n"
                "💸 قیمت نهایی: {final_price} هزار تومان\n\n"
                "⚠️ ❗️توجه:\n\n"
                "📩 بعد از تمدید - حجم باقی‌مانده ار این اکانت به دوره جدید اضافه میشه و سوخت نمیشه !\n\n"
                "⏳ اما زمان انتخابی از ابتدا ریست میشه و به زمان باقیمانده فعلی اضافه نمیشه.\n\n"
                "✅ جهت تایید نهایی تمدید اکانت و کسر مبلغ از کیف پول روی دکمه تایید خرید کلیک کنید :👇"
            ),
            lang="fa",
        )

        confirm_text = (
            confirm_text_template.replace("{service_code}", str(ConfigID))
            .replace("{plan_name}", plan_name_with_limit)
            .replace("{current_remaining_volume}", format_size(current_remaining_volume, decimal_places=0))
            .replace("{new_remaining_volume}", format_size(new_remaining_volume, decimal_places=0))
            .replace("{duration}", str(plan.duration))
            .replace("{ip_limit}", ip_limit_text)
            .replace("{discount_code}", res.code)
            .replace("{discount_amount}", f"{int(deduction):,}")
            .replace("{original_price}", f"{int(plan.price):,}")
            .replace("{final_price}", f"{int(new_amount):,}")
        )
        confirm_buttons = [
            [Button.inline("🎉 کد تخفیف اعمال شد", "none")],
            [
                Button.inline("🔙 بازگشت", data=f"service_info:{ConfigID}"),
                Button.inline("✅ تأیید خرید", data="Confirm_buy_tamdid"),
            ],
        ]
        await event.respond(confirm_text, buttons=confirm_buttons, link_preview=False)
        await set_data(event.sender_id, "codetakhfif", res.code)
        await set_data(event.sender_id, "codetakhfif_newprice", new_amount)
        await set_step(event.sender_id, "Takhfif_confirm_purchase_tamdid")
        raise events.StopPropagation

    if step == "whating_send_TransferConfig":
        if msg.isdigit():
            user_id = int(msg)

            if event.sender_id == user_id and event.sender_id not in ADMIN_ID:
                await event.respond(
                    "شما نمیتوانید کانفیگ رو به خودتون انتقال بدید",
                    buttons=await bhome_buttons(event.sender_id, lang),
                    parse_mode="html",
                )
                return
            user = await UserCRUD().read_user(user_id=user_id)
            if user:
                ConfigCode = await get_data(event.sender_id, "TransferConfig")
                config_code_int = int(ConfigCode) if ConfigCode else None
                await ServiceCRUD().update_service(code=config_code_int, id=user.id)
                # Update panel user note with new owner Telegram ID
                ok, service = (False, None)
                if config_code_int:
                    ok, service = await ServiceCRUD().get_service(config_code_int)
                if ok and service and service.in_panel and service.panel_userid:
                    try:
                        panel = await PanelsManager().get_panel_by_code(service.in_panel)
                        if panel:
                            await PasarguardAPI(panel.base_url).modify_user_by_id(
                                user_id=require_panel_userid(service),
                                user=UserModify(note=str(user.id)),
                                token=panel.cookie,
                            )
                    except Exception as e:
                        logger.warning("Failed to update panel note on transfer: %s", e)
                await event.respond(
                    f"✅کانفیگ با کد ( {ConfigCode} ) به کاربر ( {user.id} ) انتقال پیدا کرد",
                    buttons=await bhome_buttons(event.sender_id, lang),
                    parse_mode="html",
                )
                await Kenzo.send_message(
                    entity=user.id,
                    message=f"✅ کاربر عزیز یک کانفیگ با کد ( {ConfigCode} ) از کاربر ( {event.sender_id} ) برای شما واگذار شد برای مشاهده کانفیگ به بخش سرویس های من مراجعه کنید برای امنیت بیشتر یکبار کانفیگ رو تغییر لینک بدید",
                )
                await send_log_message(
                    LogType.OTHER,
                    message=f"#واگذاری_کانفیگ \nکدکانفیگ: {ConfigCode}\nتوسط: {event.sender_id} به کاربر {user.id} واگذار شد",
                )
                await clear_user(event.sender_id)
                await set_step(event.sender_id, "home")
            else:
                await event.respond(
                    "یوزر ربات رو استارت نکرده است",
                    buttons=await bhome_buttons(event.sender_id, lang),
                    parse_mode="html",
                )

        else:
            await event.respond("لطفاً فقط آیدی عددی معتبر ارسال کنید. 🙏")

    raise events.StopPropagation


async def my_services_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) == "ban":
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False

    msg = event.message.text or event.message.message or ""
    if msg == "/myaccount":
        return True
    menu_text = await get_button_text("bt.menu_my_services", "🔑 سرویس های من")
    return msg in {menu_text, "🔑 سرویس های من"}


async def service_message_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if not (event.message.message or event.message.text or ""):
        return False
    return await get_step(event.sender_id) in {
        states.SERVICE_SEARCH_INPUT_STEP,
        "WhatingForCodeTakhfifTamdid",
        "whating_send_TransferConfig",
    }


def register(client):
    client.add_event_handler(my_services_handler, events.NewMessage(incoming=True, func=my_services_filter))
    client.add_event_handler(service_message_handler, events.NewMessage(incoming=True, func=service_message_filter))

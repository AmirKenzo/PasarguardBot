"""Message handlers for user shop purchase flow."""

from __future__ import annotations

import contextlib

import httpx
from httpx import HTTPStatusError
from pasarguard import PasarguardAPI
from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.panels.nodes import filter_nodes_by_plan_type
from app.services.panels.settings import (
    calculate_custom_buy_price_from_settings,
    is_custom_buy_ready,
    panel_custom_buy_settings,
)
from app.telegram.keyboards.buy import (
    build_buy_confirm_button_rows,
    build_buy_service_selection_rows,
    buy_back_button,
    buy_cancel_button,
    buy_default_username_button,
)
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.channel_gate import ensure_channel_membership, extract_start_param
from app.telegram.shared.keyboards.panel_buttons import build_panel_display_button
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.username import (
    is_valid_username,
)
from app.telegram.state import clear_user, get_data, get_data_many, get_step, set_data, set_data_many, set_step
from app.telegram.user.shop.callbacks import (
    buy_discount_code_filter,
    buy_username_message_filter,
)
from app.telegram.user.shop.custom_buy import (
    CUSTOM_PLAN_ID,
    format_gb_value,
    validate_custom_days,
    validate_custom_gb,
)
from app.telegram.user.shop.helpers import (
    _buy_intro_text,
    _buy_username_context,
    _confirm_buy_username,
    _format_bot_text,
    _user_lang,
    resolve_buy_plan_from_session,
    show_buy_vpn_plans,
)
from app.utils.formatting.conversions import convert_storage
from app.utils.formatting.traffic import format_ip_limit
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


@bot_is_offline
async def buy_service_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    lang = await _user_lang(user_id)
    setting = await SettingsManager().get_settings()
    if setting and not setting.sale_mode:
        await event.respond("⛔️ فروش توسط ادمین بسته است.", buttons=await bhome_buttons(user_id, lang))
        raise events.StopPropagation

    panel_manager = PanelsManager()
    panels = await panel_manager.get_available_panels()

    remove_keyboard_msg = await event.respond("⏳", buttons=Button.clear())
    await remove_keyboard_msg.delete()

    if setting and setting.single_panel_buy_mode and len(panels) == 1:
        await set_step(user_id, "selectService")
        await show_buy_vpn_plans(event, panels[0], lang=lang, back_data="DataCancel")
        raise events.StopPropagation

    service_buttons = []
    for panel in panels:
        service_buttons.append(await build_panel_display_button(panel, f"BuyVPN_{panel.code}"))

    service_rows = await build_buy_service_selection_rows(service_buttons)
    await set_step(user_id, "selectService")
    buy_intro = await _buy_intro_text(lang)
    await Kenzo.send_message(entity=user_id, message=buy_intro, buttons=service_rows)
    raise events.StopPropagation


@bot_is_offline
async def custom_buy_input_handler(event: Message):
    user_id = event.sender_id
    step = await get_step(user_id)
    msg = (event.message.message or "").strip()
    session = await get_data_many(user_id, ("panel", "msgid_Buy", "gig"))
    panel_code = session.get("panel")
    panel = await PanelsManager().get_panel_by_code(panel_code)
    settings = panel_custom_buy_settings(panel) if panel else None
    if not panel or settings is None or not is_custom_buy_ready(settings):
        await event.respond("❌ خرید دلخواه برای این پنل فعال نیست.")
        await clear_user(user_id)
        await set_step(user_id, "home")
        raise events.StopPropagation

    back_buttons = [[await buy_back_button(f"BuyVPN_{panel.code}")], [await buy_cancel_button("DataCancel")]]
    msgid = session.get("msgid_Buy")

    async def _edit(text: str, buttons=None) -> None:
        with contextlib.suppress(Exception):
            await event.delete()
        if msgid:
            with contextlib.suppress(Exception):
                await event.client.edit_message(event.chat_id, int(msgid), text, buttons=buttons or back_buttons)
                return
        await event.respond(text, buttons=buttons or back_buttons)

    if step == "custom_buy_enter_gb":
        value, error = validate_custom_gb(panel, msg, settings=settings)
        if error:
            await _edit(error)
            raise events.StopPropagation
        await set_data_many(
            user_id,
            {
                "gig": value,
                "selected_plan_id": CUSTOM_PLAN_ID,
            },
        )
        await set_step(user_id, "custom_buy_enter_days")
        days_prompt = await _format_bot_text(
            key="custom_buy_enter_days_message",
            default=("✅ حجم `{gb}` گیگ ثبت شد.\n\n⏰ تعداد روز را وارد کنید (بین `{min_days}` تا `{max_days}`):"),
            lang=await _user_lang(user_id),
            gb=format_gb_value(value),
            min_days=settings["min_days"],
            max_days=settings["max_days"],
        )
        await _edit(days_prompt)
        raise events.StopPropagation

    if step == "custom_buy_enter_days":
        days, error = validate_custom_days(panel, msg, settings=settings)
        if error:
            await _edit(error)
            raise events.StopPropagation
        gig = session.get("gig")
        if gig is None:
            await set_step(user_id, "custom_buy_enter_gb")
            await _edit("❌ ابتدا حجم را وارد کنید.")
            raise events.StopPropagation

        price = calculate_custom_buy_price_from_settings(settings, storage_gb=float(gig), duration_days=days)
        await set_data_many(
            user_id,
            {
                "custom_days": days,
                "custom_price": price,
                "custom_ip_limit": int(settings["ip_limit"]),
                "selected_plan_id": CUSTOM_PLAN_ID,
            },
        )
        await set_step(user_id, "enter_username")
        username_message = await get_bot_text(
            key="enter_username_message",
            default=(
                "🔸 یک نام برای کانفیگ وارد کنید:\n"
                "^qc^نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.\n"
                "نمونه:\nAmir_Kenzo123\nNeda\nNeda123\nNeda_123^qc^"
            ),
            lang=await _user_lang(user_id),
        )
        await _edit(
            f"**🧩 خرید دلخواه**\n"
            f"📥 حجم: `{format_gb_value(float(gig))}` گیگ\n"
            f"⏰ مدت: `{days}` روز\n"
            f"💸 قیمت: `{price:,}` تومان\n\n"
            f"{username_message}",
            buttons=[
                [await buy_default_username_button(b"generate_username")],
                [await buy_cancel_button(b"DataCancel")],
            ],
        )
        raise events.StopPropagation


@bot_is_offline
async def buy_username_message_handler(event: Message):
    username = (event.message.message or "").strip()
    panel, _gig, _plan = await _buy_username_context(event.sender_id)
    retry_buttons = [
        [await buy_default_username_button(b"generate_username")],
        [await buy_cancel_button(b"DataCancel")],
    ]
    if not is_valid_username(username):
        await event.respond(
            "❌ نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.",
            buttons=retry_buttons,
        )
        raise events.StopPropagation
    try:
        await PasarguardAPI(panel.base_url).get_user_by_username(username=username, token=panel.cookie)
        await event.respond(
            "❌ نام کاربری توسط شخص دیگری ساخته شده\n\n^q^لطفا نام کاربری دیگری ارسال کنید یا اینکه روی دکمه زیر کلیک کنید تا اسم رندوم ساخته شود^q^",
            buttons=retry_buttons,
        )
        raise events.StopPropagation
    except HTTPStatusError as e:
        if e.response.status_code != 404:
            await event.respond("خطا در ارتباط با پنل", buttons=retry_buttons)
            raise events.StopPropagation from None

    await _confirm_buy_username(event, username, edit=False)
    raise events.StopPropagation


@bot_is_offline
async def buy_discount_code_handler(event: Message):
    msg = event.message.message
    lang = await _user_lang(event.sender_id)
    status, res = await DiscountCodeManager().validate_discount_code(code=msg, user_id=event.sender_id)
    msgid_buy = await get_data(event.sender_id, "msgid_Buy")
    await event.client.delete_messages(event.chat_id, msgid_buy)
    if not status:
        await event.respond(f"{res}", buttons=await bhome_buttons(event.sender_id, lang))
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "home")
        raise events.StopPropagation

    panel_code = await get_data(event.sender_id, "panel")
    gig = await get_data(event.sender_id, "gig")
    username = await get_data(event.sender_id, "username")
    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    plan = await resolve_buy_plan_from_session(event.sender_id)
    if plan is None:
        await event.respond("خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(event.sender_id, lang))
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "home")
        raise events.StopPropagation
    new_amount = int(plan.price - (plan.price * (res.discount_percentage / 100)))

    try:
        api = PasarguardAPI(base_url=panel.base_url)
        nodes_stats = await api.get_nodes(token=panel.cookie)
        filtered_nodes = filter_nodes_by_plan_type(nodes_stats.nodes, plan, panel)
        locations = " ⌁ ".join([f"{node.name}" for node in filtered_nodes]) or " "
    except httpx.HTTPStatusError as e:
        locations = (
            "🇺🇸 🇹🇷 🇫🇮 🇩🇪 🇦🇲 " if e.response.status_code == 403 else "❌ خطا در دریافت نودها، لطفاً دوباره تلاش کنید."
        )

    ip_limit_text = format_ip_limit(getattr(plan, "ip_limit", 0))
    volume_text = convert_storage(
        float(gig), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
    )
    confirm_text_template = await get_bot_text(
        key="config_purchase_discount_confirm",
        default=(
            "**ساخت کانفیگ اختصاصی V2Ray با مشخصات زیر را تأیید می‌کنید؟**\n\n"
            "**▪️ حجم سرویس :** {volume}\n"
            "**⏰ مدت زمان :** {duration} روز\n"
            "**▫️نام کانفیگ :** `{config_name}`\n"
            "**▫️نوع کانفیگ :** {config_type}\n"
            "**▫️ لوکیشن های موجودسرویس :** \n**^qc^{locations}^qc^**\n"
            "**🔌 محدودیت کاربر :** {user_limit}\n"
            "**💸 مبلغ قبل:** `{original_price}` **مبلغ جدید:** `{new_price}`\n"
            "❗️ نکته؛\n"
            "(پس از خرید؛ امکان افزایش حجم وجود دارد و همچنین مقدار باقیمانده حجم و روز از بخش سرویس‌های من قابل مشاهده است)"
        ),
        lang="fa",
    )
    confirm_text = (
        confirm_text_template.replace("{volume}", volume_text)
        .replace("{duration}", str(plan.duration))
        .replace("{config_name}", username or "")
        .replace("{config_type}", panel.name)
        .replace("{locations}", locations)
        .replace("{user_limit}", ip_limit_text)
        .replace("{original_price}", f"{int(plan.price):,}")
        .replace("{new_price}", f"{int(new_amount):,}")
    )
    confirm_buttons = [
        [Button.inline("🎉 کد تخفیف اعمال شد", "none")],
        *(await build_buy_confirm_button_rows(confirm_data="Confirm_buy", with_discount=False)),
    ]
    await event.respond(confirm_text, buttons=confirm_buttons, link_preview=False)
    await set_data(event.sender_id, "codetakhfif", res.code)
    await set_data(event.sender_id, "codetakhfif_newprice", new_amount)
    await set_step(event.sender_id, "Takhfif_confirm_purchase")
    raise events.StopPropagation


async def custom_buy_input_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    text = (event.message.message or "").strip()
    if not text or text.startswith("/"):
        return False
    return await get_step(event.sender_id) in {"custom_buy_enter_gb", "custom_buy_enter_days"}


async def buy_service_filter(event: Message) -> bool:
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
    if param and param.lower() == "buy":
        return True
    if msg == "/buy":
        return True
    menu_text = await get_button_text("bt.menu_buy_service", "🛍 خرید سرویس")
    return msg in {menu_text, "🛍 خرید سرویس"}


async def account_discount_message_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if not (event.message.message or event.message.text or ""):
        return False
    return await get_step(event.sender_id) == "WhatingForAccountCodeTakhfif"


def register(client):
    client.add_event_handler(buy_service_handler, events.NewMessage(incoming=True, func=buy_service_filter))
    client.add_event_handler(custom_buy_input_handler, events.NewMessage(incoming=True, func=custom_buy_input_filter))
    client.add_event_handler(
        buy_username_message_handler, events.NewMessage(incoming=True, func=buy_username_message_filter)
    )
    client.add_event_handler(buy_discount_code_handler, events.NewMessage(incoming=True, func=buy_discount_code_filter))

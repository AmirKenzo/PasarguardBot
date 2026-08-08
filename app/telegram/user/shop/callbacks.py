"""Callback handlers for user shop purchase flow."""

from __future__ import annotations

from telethon import events
from telethon.tl.custom import Message

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.billing.sticky_discount import discounted_price, get_sticky_discount
from app.services.panels.settings import is_custom_buy_ready, panel_custom_buy_settings
from app.telegram.keyboards.buy import (
    build_buy_username_prompt_rows,
    buy_back_button,
    buy_cancel_button,
)
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.callback_guards import notify_session_expired
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.username import (
    generate_unique_username,
)
from app.telegram.state import get_data, get_step, set_data, set_data_many, set_step
from app.telegram.user.shop.custom_buy import CUSTOM_PLAN_ID, format_gb_value
from app.telegram.user.shop.helpers import (
    _buy_username_context,
    _complete_vpn_purchase,
    _confirm_buy_username,
    _format_bot_text,
    _load_purchase_context,
    _show_buy_username_prompt,
    _user_lang,
    clear_custom_buy_session,
    generate_volume_buttons,
    resolve_buy_plan_from_session,
    show_buy_service_selection,
    show_buy_vpn_plans,
)
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def buy_username_message_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    text = (event.message.message or "").strip()
    if not text or text.startswith("/"):
        return False
    return await get_step(event.sender_id) == "enter_username"


async def buy_discount_code_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    text = (event.message.message or "").strip()
    if not text or text.startswith("/"):
        return False
    return await get_step(event.sender_id) == "WhatingForCodeTakhfif"


@bot_is_offline
async def back_to_panels_callback(event: events.CallbackQuery.Event):
    setting = await SettingsManager().get_settings()
    if setting and not setting.sale_mode:
        await event.answer("⛔️ فروش توسط ادمین بسته است.", alert=True)
        raise events.StopPropagation
    await show_buy_service_selection(event, lang=await _user_lang(event.sender_id), use_panel_rows=True)
    raise events.StopPropagation


@bot_is_offline
async def buy_vpn_panel_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    selected_code = data.replace("BuyVPN_", "")
    selected_panel = await PanelsManager().get_panel_by_code(selected_code)
    if not selected_panel:
        await event.answer("❌ پنل یافت نشد!", alert=True)
        raise events.StopPropagation

    await show_buy_vpn_plans(event, selected_panel, lang=await _user_lang(event.sender_id), back_data="backtopanels")
    raise events.StopPropagation


@bot_is_offline
async def select_duration_group_for_buy_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    parts = data.split(":")
    panel_code = parts[1]
    duration_value = int(parts[2])

    selected_panel = await PanelsManager().get_panel_by_code(panel_code)
    if not selected_panel:
        await event.answer("❌ پنل یافت نشد!", alert=True)
        raise events.StopPropagation

    panel_volume_text = await get_bot_text(
        key="buy_select_panel_volume_message",
        default="✅ شما پنل **{panel_name}** رو انتخاب کردید :\n\n📊 لطفاً تعرفه مورد نظر خود را انتخاب کنید:",
        lang=await _user_lang(event.sender_id),
    )
    formatted_message = panel_volume_text.replace("{panel_name}", selected_panel.name)

    await event.edit(
        formatted_message,
        buttons=await generate_volume_buttons(panel_code, duration_group=[duration_value]),
    )
    await set_step(event.sender_id, "selectData")
    raise events.StopPropagation


@bot_is_offline
async def select_plan_for_buy_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "selectData":
        await notify_session_expired(event)
        return

    data = event.data.decode("utf-8")
    plan_id = int(data.split("_")[1])
    plan = await PlanManager().get_plan(plan_id)
    if not plan:
        await event.answer("❌ پلن یافت نشد!", alert=True)
        raise events.StopPropagation

    await clear_custom_buy_session(event.sender_id)
    await set_data(event.sender_id, "gig", plan.storage)
    await set_data(event.sender_id, "selected_plan_id", plan_id)

    panel_code = await get_data(event.sender_id, "panel")
    await PanelsManager().get_panel_by_code(code=panel_code)

    await set_step(event.sender_id, "enter_username")
    username_message = await get_bot_text(
        key="enter_username_message",
        default=(
            "🔸 یک نام برای کانفیگ وارد کنید:\n"
            "^qc^نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.\n"
            "نمونه:\nAmir_Kenzo123\nNeda\nNeda123\nNeda_123^qc^"
        ),
        lang=await _user_lang(event.sender_id),
    )
    await event.edit(
        username_message,
        buttons=await build_buy_username_prompt_rows(),
    )
    raise events.StopPropagation


@bot_is_offline
async def retry_buy_username_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "enter_username":
        await notify_session_expired(event)
        return
    await _show_buy_username_prompt(event)
    raise events.StopPropagation


@bot_is_offline
async def generate_buy_username_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "enter_username":
        await notify_session_expired(event)
        return
    panel, _gig, _plan = await _buy_username_context(event.sender_id)
    username = await generate_unique_username(panel)
    await _confirm_buy_username(event, username, edit=True)
    raise events.StopPropagation


@bot_is_offline
async def custom_buy_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    panel_code = data.replace("CustomBuy_", "")
    panel = await PanelsManager().get_panel_by_code(panel_code)
    settings = panel_custom_buy_settings(panel) if panel else None
    if not panel or settings is None or not is_custom_buy_ready(settings):
        await event.answer("❌ خرید دلخواه برای این پنل فعال نیست.", alert=True)
        raise events.StopPropagation

    await clear_custom_buy_session(event.sender_id)
    await set_data_many(
        event.sender_id,
        {
            "panel": panel.code,
            "selected_plan_id": CUSTOM_PLAN_ID,
        },
    )
    await set_step(event.sender_id, "custom_buy_enter_gb")
    gb_prompt = await _format_bot_text(
        key="custom_buy_enter_gb_message",
        default=(
            "**🧩 خرید دلخواه — {panel_name}**\n\n"
            "💰 هر گیگ: `{price_per_gb}` تومان\n"
            "⏰ هر روز: `{price_per_day}` تومان\n\n"
            "📥 حجم مورد نظر را به گیگ وارد کنید "
            "(بین `{min_gb}` تا `{max_gb}`):"
        ),
        lang=await _user_lang(event.sender_id),
        panel_name=panel.name,
        price_per_gb=f"{settings['price_per_gb']:,}",
        price_per_day=f"{settings['price_per_day']:,}",
        min_gb=format_gb_value(settings["min_gb"]),
        max_gb=format_gb_value(settings["max_gb"]),
    )
    await event.edit(
        gb_prompt,
        buttons=[[await buy_back_button(f"BuyVPN_{panel.code}")], [await buy_cancel_button("DataCancel")]],
    )
    await set_data(event.sender_id, "msgid_Buy", event.message_id)
    raise events.StopPropagation


@bot_is_offline
async def apply_buy_discount_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "crconf":
        await notify_session_expired(event)
        return
    mag_id = await event.edit(
        "**🎉 کد تخفیف جادویی خود را وارد کنید!**\n💰 برای اعمال تخفیف ویژه، کد خود را همین حالا ارسال کنید! 🚀",
        parse_mode="md",
        link_preview=False,
        buttons=[[await buy_cancel_button("DataCancel")]],
    )
    await set_data(event.sender_id, "msgid_Buy", mag_id.id)
    await set_step(event.sender_id, "WhatingForCodeTakhfif")
    raise events.StopPropagation


@bot_is_offline
async def confirm_discounted_buy_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "Takhfif_confirm_purchase":
        await notify_session_expired(event)
        return
    plan = await resolve_buy_plan_from_session(event.sender_id)
    new_price = await get_data(event.sender_id, "codetakhfif_newprice")
    code_takhfif = await get_data(event.sender_id, "codetakhfif")
    if plan is None or new_price is None or code_takhfif is None:
        await event.edit(
            "خطا: اطلاعات مورد نیاز پیدا نشد.",
            buttons=await bhome_buttons(event.sender_id, await _user_lang(event.sender_id)),
        )
        raise events.StopPropagation
    try:
        new_price = int(float(new_price))
    except ValueError, TypeError:
        new_price = int(plan.price)
    status, _res = await DiscountCodeManager().validate_discount_code(code=code_takhfif, user_id=event.sender_id)
    if not status:
        await event.edit(
            "کد تخفیف معتبر نیست.", buttons=await bhome_buttons(event.sender_id, await _user_lang(event.sender_id))
        )
        raise events.StopPropagation
    await _complete_vpn_purchase(event, amount=new_price, discount_code=code_takhfif)
    raise events.StopPropagation


@bot_is_offline
async def confirm_buy_callback(event: events.CallbackQuery.Event):
    if await get_step(event.sender_id) != "crconf":
        await notify_session_expired(event)
        return
    _gig, _panel_code, plan = await _load_purchase_context(event.sender_id)
    if plan is None:
        await event.edit(
            "خطا: اطلاعات مورد نیاز پیدا نشد.",
            buttons=await bhome_buttons(event.sender_id, await _user_lang(event.sender_id)),
        )
        raise events.StopPropagation
    sticky = await get_sticky_discount(event.sender_id)
    if sticky:
        new_price = discounted_price(plan.price, sticky.discount_percentage)
        await _complete_vpn_purchase(event, amount=new_price, discount_code=sticky.code)
    else:
        await _complete_vpn_purchase(event, amount=int(plan.price))
    raise events.StopPropagation


def register(client):
    client.add_event_handler(back_to_panels_callback, events.CallbackQuery(data="backtopanels"))
    client.add_event_handler(buy_vpn_panel_callback, events.CallbackQuery(pattern=rb"^BuyVPN_"))
    client.add_event_handler(
        select_duration_group_for_buy_callback, events.CallbackQuery(pattern=rb"^SelectDurationGroupForBuy:")
    )
    client.add_event_handler(select_plan_for_buy_callback, events.CallbackQuery(pattern=rb"^SelectPlan_"))
    client.add_event_handler(custom_buy_callback, events.CallbackQuery(pattern=rb"^CustomBuy_"))
    client.add_event_handler(retry_buy_username_callback, events.CallbackQuery(data="retry_buy_username"))
    client.add_event_handler(generate_buy_username_callback, events.CallbackQuery(data="generate_username"))
    client.add_event_handler(apply_buy_discount_callback, events.CallbackQuery(pattern=rb"^ApplyCodeTakhfif"))
    client.add_event_handler(confirm_discounted_buy_callback, events.CallbackQuery(data="Confirm_buy"))
    client.add_event_handler(confirm_buy_callback, events.CallbackQuery(pattern=rb"^confirm_purchase_"))

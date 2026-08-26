"""Shared helpers for user shop purchase flow."""

from __future__ import annotations

import random
import time

import httpx
from httpx import HTTPStatusError
from pasarguard import PasarguardAPI, UserCreate
from pasarguard.enums import UserDataLimitResetStrategy
from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, update_Money
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_flow import (
    build_insufficient_balance_message,
    create_balance_button,
)
from app.services.billing.direct_pay_store import KIND_VPN
from app.services.billing.referral_rewards import process_referral_reward_payout
from app.services.billing.sticky_discount import discounted_price, get_sticky_discount
from app.services.panels.auth import fetch_panel_groups_with_auth
from app.services.panels.config_links import get_selected_single_config_links_text
from app.services.panels.custom_buy import build_custom_buy_plan, is_custom_plan_id
from app.services.panels.groups import resolve_panel_group_ids
from app.services.panels.nodes import filter_nodes_by_plan_type, format_node_name_for_display
from app.services.panels.settings import (
    panel_custom_buy_enabled,
    panel_display_mode,
    panel_shop_sale_enabled,
    panel_user_limit,
)
from app.services.subscriptions.links import format_subscription_links_for_message
from app.telegram.keyboards.buy import (
    build_buy_confirm_button_rows,
    build_buy_service_selection_rows,
    build_buy_username_prompt_rows,
    buy_back_button,
    buy_custom_button,
)
from app.telegram.keyboards.common import styled_copy_button, styled_webview_button
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.keyboards.duration_buttons import build_duration_selection_button_rows
from app.telegram.shared.keyboards.panel_buttons import build_panel_display_button
from app.telegram.shared.keyboards.plan_buttons import build_plan_inline_button
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.media import respond_with_photo_and_text, send_photo_and_text_to_user
from app.telegram.shared.utils.username import (
    handle_buy_username_conflict,
    is_panel_username_conflict,
)
from app.telegram.state import clear_user, delete_data_many, get_data, get_data_many, set_data, set_step
from app.telegram.user.shop import states
from app.utils.formatting.conversions import convert_storage, day_to_timestamp, gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_ip_limit
from app.utils.media.qrcode import create_qr_code
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def _user_lang(user_id: int) -> str:
    info = await UserCRUD().read_user(user_id)
    return info.language if info and info.language else states.BOT_LANGUAGE


async def _format_bot_text(key: str, default: str, lang: str, **placeholders: object) -> str:
    template = await get_bot_text(key=key, default=default, lang=lang)
    for name, value in placeholders.items():
        template = template.replace(f"{{{name}}}", str(value))
    return template


async def check_user_balance(user_id: int, required_amount: int):
    user = await UserCRUD().read_user(user_id=user_id)
    if user is None:
        return False, "کاربر یافت نشد."

    balance = user.amount
    required = int(required_amount)
    if balance < 0:
        return False, "موجودی شما منفی است. لطفاً موجودی خود را بررسی کنید."
    if balance == 0 or balance < required:
        return False, ""
    return True, "موجودی کافی است."


async def _buy_intro_text(lang: str) -> str:
    return await get_bot_text(
        key="buy_service_intro",
        default=(
            "**🎉 سرویس معمولی مستقیم** ^q^شامل کانفیگ‌های مستقیم و سی‌دی‌ان برای اتصال ساده.^q^\n"
            "**🌍 سرویس تانل:** ^q^علاوه بر سرویس‌های معمولی، این سرویس شامل سرویس‌های تانل‌شده است "
            "که در صورت فیلتر شدن آی‌پی، بدون مشکل و به راحتی کار خواهد کرد. "
            "(در حالی که سرویس معمولی در چنین شرایطی ممکن است دچار مشکل شود.)^q^\n\n"
            "**💬 لطفاً پنل مورد نظر خود را انتخاب کنید:**"
        ),
        lang=lang,
    )


def group_durations(durations):
    """English docstring for group_durations."""
    individual_durations = {}
    for duration in durations:
        individual_durations[f"{duration} روزه"] = [duration]
    return individual_durations


async def generate_volume_buttons(panel_code, duration=None, duration_group=None, *, back_data="backtopanels"):
    """English docstring for generate_volume_buttons."""
    try:
        if duration_group:
            plans = await PlanManager().get_all_plans(panel_code=panel_code)
            plans = [p for p in plans if p.duration in duration_group]
        else:
            plans = await PlanManager().get_all_plans(panel_code=panel_code, duration=duration)

        panel = await PanelsManager().get_panel_by_code(panel_code)
        volume_buttons = []
        if plans:
            sorted_plans = sorted(plans, key=lambda plan: plan.storage)
            volume_buttons = [
                [await build_plan_inline_button(plan, panel, f"SelectPlan_{plan.id}", context="buy")]
                for plan in sorted_plans
            ]
        if panel and panel_custom_buy_enabled(panel):
            volume_buttons.append([await buy_custom_button(f"CustomBuy_{panel_code}")])
        if not volume_buttons:
            return [[Button.inline("❌ هیچ پلنی برای این پنل یافت نشد", data="no_plans")]]
        volume_buttons.append([await buy_back_button(back_data)])
        return volume_buttons
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌ها: {e}")
        return [[Button.inline("⚠️ خطا در دریافت پلن‌ها", data="error")]]


async def resolve_buy_plan_from_session(user_id: int):
    session = await get_data_many(
        user_id,
        ("selected_plan_id", "gig", "custom_days", "custom_price", "custom_ip_limit"),
    )
    plan_id = session.get("selected_plan_id")
    if is_custom_plan_id(plan_id):
        gig = session.get("gig")
        days = session.get("custom_days")
        price = session.get("custom_price")
        ip_limit = session.get("custom_ip_limit")
        if gig is None or days is None or price is None:
            return None
        return build_custom_buy_plan(
            storage_gb=float(gig),
            duration_days=int(days),
            price=int(float(price)),
            ip_limit=int(ip_limit or 0),
        )
    if plan_id is None:
        return None
    return await PlanManager().get_plan(plan_id)


async def clear_custom_buy_session(user_id: int) -> None:
    await delete_data_many(user_id, ("custom_days", "custom_price", "custom_ip_limit"))


async def build_buy_panel_rows(panels: list) -> list:
    panel_buttons = [await build_panel_display_button(panel, f"BuyVPN_{panel.code}") for panel in panels]
    return await build_buy_service_selection_rows(panel_buttons)


async def show_buy_service_selection(event, *, lang: str, use_panel_rows: bool = False) -> None:
    panel_manager = PanelsManager()
    panels = await panel_manager.get_available_panels()
    settings = await SettingsManager().get_settings()
    await set_step(event.sender_id, "selectLocation")

    if use_panel_rows:
        if settings and settings.single_panel_buy_mode and len(panels) == 1:
            await show_buy_vpn_plans(event, panels[0], lang=lang, back_data="DataCancel")
            return
        rows = await build_buy_panel_rows(panels)
    else:
        all_panels = [panel for panel in await PanelsManager().get_all_panels() if panel_shop_sale_enabled(panel)]
        available_panels = await PanelsManager().get_available_panels()
        if settings and settings.single_panel_buy_mode and len(available_panels) == 1:
            await show_buy_vpn_plans(event, available_panels[0], lang=lang, back_data="DataCancel")
            return

        service_buttons = [await build_panel_display_button(panel, f"BuyVPN_{panel.code}") for panel in all_panels]
        rows = await build_buy_service_selection_rows(service_buttons)

    await event.edit(await _buy_intro_text(lang), buttons=rows)


async def show_buy_vpn_plans(event, panel, *, lang: str = "fa", back_data: str = "backtopanels") -> None:
    """Show plan/volume selection for a VPN panel (BuyVPN_ flow)."""
    selected_code = panel.code
    user_id = event.sender_id
    is_callback = hasattr(event, "answer")

    if not panel_shop_sale_enabled(panel):
        msg = "⛔️ این پنل در فروش سرویس فعال نیست!"
        if is_callback:
            await event.answer(msg, alert=True)
        else:
            await event.respond(msg)
        return

    panel_manager = PanelsManager()
    if await panel_manager.is_panel_at_capacity(selected_code):
        current_services = await panel_manager.count_panel_users(selected_code)
        msg = (
            f"⚠️ ظرفیت پنل {panel.name} تکمیل شده است!\n\n"
            f"📊 تعداد کانفیگ‌های فعلی: {current_services}/{panel_user_limit(panel)}\n\n"
            f"💡 لطفاً پنل دیگری را انتخاب کنید."
        )
        if is_callback:
            await event.answer(msg, alert=True)
        else:
            await event.respond(msg)
        return

    display_mode = panel_display_mode(panel)
    custom_enabled = panel_custom_buy_enabled(panel)
    if display_mode == "duration_first":
        durations = await PlanManager().get_unique_durations(selected_code)
        duration_groups = group_durations(durations) if durations else []
        if not duration_groups and not custom_enabled:
            msg = "❌ هیچ پلنی برای این پنل موجود نیست!"
            if is_callback:
                await event.answer(msg, alert=True)
            else:
                await event.respond(msg)
            return

        back_row = [await buy_back_button(back_data)]
        if duration_groups:
            buttons = await build_duration_selection_button_rows(
                selected_code,
                duration_groups,
                context="buy",
                make_callback=lambda d: f"SelectDurationGroupForBuy:{selected_code}:{d}",
                back_row=back_row,
            )
        else:
            buttons = [back_row]
        if custom_enabled:
            custom_row = [await buy_custom_button(f"CustomBuy_{selected_code}")]
            if buttons and buttons[-1] == back_row:
                buttons.insert(-1, custom_row)
            else:
                buttons.append(custom_row)
                buttons.append(back_row)
        message = await get_bot_text(
            key="buy_select_duration_message",
            default="⚡️ یکی از پلن های موجود رو از ۷ روزه تا ۹۰ روزه انتخاب کن :",
            lang=lang,
        )
    else:
        panel_volume_text = await get_bot_text(
            key="buy_select_panel_volume_message",
            default="شما پنل **{panel_name}** را انتخاب کردید. لطفاً حجم را انتخاب کنید::",
            lang=lang,
        )
        message = panel_volume_text.replace("{panel_name}", panel.name)
        buttons = await generate_volume_buttons(selected_code, back_data=back_data)
        if buttons and len(buttons) == 1 and buttons[0] and getattr(buttons[0][0], "data", b"") == b"no_plans":
            msg = "❌ هیچ پلنی برای این پنل موجود نیست!"
            if is_callback:
                await event.answer(msg, alert=True)
            else:
                await event.respond(msg)
            return
        await set_step(user_id, "selectData")

    await set_data(user_id, "panel", selected_code)

    if is_callback:
        await event.edit(message, buttons=buttons)
    else:
        await Kenzo.send_message(entity=user_id, message=message, buttons=buttons)


async def _buy_username_context(user_id: int):
    session = await get_data_many(user_id, ("panel", "gig"))
    panel_code = session.get("panel")
    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    gig = session.get("gig")
    plan = await resolve_buy_plan_from_session(user_id)
    return panel, gig, plan


async def _buy_plan_locations(panel, plan) -> str:
    try:
        api = PasarguardAPI(base_url=panel.base_url)
        nodes_stats = await api.get_nodes(token=panel.cookie)
        filtered_nodes = filter_nodes_by_plan_type(nodes_stats.nodes, plan, panel)
        return " ⌁ ".join([format_node_name_for_display(node.name, panel) for node in filtered_nodes]) or " "
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return "🇺🇸 🇹🇷 🇫🇮 🇩🇪 🇦🇲 "
        return "❌ خطا در دریافت نودها، لطفاً دوباره تلاش کنید."


async def _buy_confirm_text(*, username: str, panel, gig, plan, lang: str) -> str:
    locations = await _buy_plan_locations(panel, plan)
    ip_limit_text = format_ip_limit(getattr(plan, "ip_limit", 0))
    volume_text = convert_storage(
        float(gig), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
    )
    template = await get_bot_text(
        key="config_purchase_confirm",
        default=(
            "ساخت کانفیگ اختصاصی V2Ray با مشخصات زیر را تأیید می‌کنید؟\n\n"
            "**▪️ حجم سرویس :** {volume}\n"
            "**⏰ مدت زمان :** {duration} روز\n"
            "**▫️نام کانفیگ :** `{config_name}`\n"
            "**▫️نوع کانفیگ :** {config_type}\n"
            "**▫️ لوکیشن های موجودسرویس :** \n**^qc^{locations}^qc^**\n"
            "**🔌 محدودیت کاربر :** {user_limit}\n"
            "**💸 قیمت نهایی :** {price} هزار تومان\n\n"
            "^q^پس از خرید، امکان افزایش حجم و زمان وجود دارد. مقدار باقی‌مانده‌ی حجم و روزها از بخش «سرویس‌های من» قابل مشاهده است.^q^"
        ),
        lang=lang,
    )
    return (
        template.replace("{volume}", volume_text)
        .replace("{duration}", str(plan.duration))
        .replace("{config_name}", username)
        .replace("{config_type}", panel.name)
        .replace("{locations}", locations)
        .replace("{user_limit}", ip_limit_text)
        .replace("{price}", f"{int(plan.price):,}")
    )


async def _show_buy_username_prompt(event) -> None:
    username_message = await get_bot_text(
        key="enter_username_message",
        default=(
            "🔸 یک نام برای کانفیگ وارد کنید:\n"
            "^qc^نام کاربری باید بین ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، اعداد و زیرخط باشد.\n"
            "نمونه:\nAmir_Kenzo123\nNeda\nNeda123\nNeda_123^qc^"
        ),
        lang=await _user_lang(event.sender_id),
    )
    await event.edit(username_message, buttons=await build_buy_username_prompt_rows())


async def _confirm_buy_username(event, username: str, *, edit: bool) -> None:
    panel, gig, plan = await _buy_username_context(event.sender_id)
    lang = await _user_lang(event.sender_id)
    confirm_text = await _buy_confirm_text(
        username=username,
        panel=panel,
        gig=gig,
        plan=plan,
        lang=lang,
    )
    sticky = await get_sticky_discount(event.sender_id)
    if sticky:
        new_price = discounted_price(plan.price, sticky.discount_percentage)
        confirm_text = (
            f"{confirm_text}\n\n"
            f"🎟 **تخفیف فعال:** `{sticky.code}` (`{sticky.discount_percentage}%`)\n"
            f"💸 **قیمت با تخفیف:** `{new_price:,}` تومان"
        )
        confirm_buttons = [
            [Button.inline("🎉 تخفیف فعال روی حساب شما", "none")],
            *(await build_buy_confirm_button_rows(confirm_data="Confirm_buy", with_discount=False)),
        ]
        await set_data(event.sender_id, "codetakhfif", sticky.code)
        await set_data(event.sender_id, "codetakhfif_newprice", new_price)
        await set_step(event.sender_id, "Takhfif_confirm_purchase")
    else:
        confirm_buttons = await build_buy_confirm_button_rows(
            confirm_data=f"confirm_purchase_{panel.code}_{gig}",
        )
        await set_step(event.sender_id, "crconf")
    await set_data(event.sender_id, "username", username)
    if edit:
        await event.edit(confirm_text, buttons=confirm_buttons, link_preview=False)
    else:
        await event.respond(confirm_text, buttons=confirm_buttons, link_preview=False)


async def _load_purchase_context(user_id: int):
    session = await get_data_many(user_id, ("gig", "panel"))
    gig = session.get("gig")
    panel_code = session.get("panel")
    plan = await resolve_buy_plan_from_session(user_id)
    return gig, panel_code, plan


async def create_vpn_purchase_for_user(
    user_id: int,
    *,
    amount: int,
    payload: dict | None = None,
    discount_code: str | None = None,
    event=None,
) -> tuple[bool, str]:
    """Create VPN config, deduct wallet, notify user. Works with or without a Telethon event."""
    lang = await _user_lang(user_id)
    if payload:
        gig = payload.get("gig")
        panel_code = payload.get("panel")
        plan_id = payload.get("selected_plan_id", payload.get("plan_id"))
        username = payload.get("username")
        discount_code = discount_code or payload.get("discount_code")
        if is_custom_plan_id(plan_id):
            days = payload.get("custom_days")
            price = payload.get("custom_price")
            ip_limit = payload.get("custom_ip_limit")
            if gig is None or days is None or price is None:
                plan = None
            else:
                plan = build_custom_buy_plan(
                    storage_gb=float(gig),
                    duration_days=int(days),
                    price=int(float(price)),
                    ip_limit=int(ip_limit or 0),
                )
        else:
            plan = await PlanManager().get_plan(plan_id)
    else:
        gig, panel_code, plan = await _load_purchase_context(user_id)
        username = await get_data(user_id, "username")

    if gig is None or panel_code is None or plan is None or not username:
        if event is not None:
            await event.edit("خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(user_id, lang))
        else:
            await Kenzo.send_message(
                user_id, "خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(user_id, lang)
            )
        return False, "missing_context"

    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    if not panel:
        msg = "پنل یافت نشد."
        if event is not None:
            await event.edit(msg, buttons=await bhome_buttons(user_id, lang))
        else:
            await Kenzo.send_message(user_id, msg, buttons=await bhome_buttons(user_id, lang))
        return False, "panel_not_found"

    code_service = random.randint(10000, 9999999)
    groups_resp = await fetch_panel_groups_with_auth(panel)
    group_ids = resolve_panel_group_ids(panel, groups_resp)

    reset_strategy = UserDataLimitResetStrategy.NO_RESET
    if plan.plan_type in ["fair_usage", "fair"] and plan.data_limit_reset_strategy:
        reset_strategy = UserDataLimitResetStrategy(plan.data_limit_reset_strategy)

    start_time = time.time()
    ip_limit = getattr(plan, "ip_limit", 0) or 0
    new_user = UserCreate(
        username=username,
        group_ids=group_ids,
        data_limit=gigabytes_to_bytes(float(gig)),
        expire=day_to_timestamp(int(plan.duration)),
        note=f"{user_id}",
        data_limit_reset_strategy=reset_strategy,
        hwid_limit=ip_limit if ip_limit > 0 else None,
    )
    try:
        added_user = await PasarguardAPI(panel.base_url).add_user(user=new_user, token=panel.cookie)
    except HTTPStatusError as e:
        if is_panel_username_conflict(e):
            if event is not None:
                await handle_buy_username_conflict(event, username)
            else:
                await Kenzo.send_message(
                    user_id,
                    f"نام کاربری `{username}` تکراری است. لطفاً دوباره خرید را انجام دهید.",
                    buttons=await bhome_buttons(user_id, lang),
                )
            return False, "username_conflict"
        raise

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
        main_label="🔗 لینک سابسکریپشن",
        tunnel_label="🌐 لینک تانل سابسکریپشن",
    )
    single_config_links_text = await get_selected_single_config_links_text(panel, getattr(added_user, "id", None))
    single_config_links_section = (
        f"**🔗 لینک‌های تکی انتخاب‌شده:**\n{single_config_links_text}" if single_config_links_text else ""
    )
    qr_file = create_qr_code(text=f"{primary_subscription_url}", filename=f"{code_service}.png")
    if event is not None:
        await event.delete()
    new_amount = await update_Money(user_id=user_id, Money=-int(amount))
    ip_limit_text = format_ip_limit(getattr(plan, "ip_limit", 0))
    volume_text = convert_storage(
        float(gig), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
    )

    txt_template = await get_bot_text(
        key="config_purchase_success_message",
        default=(
            "**🎉 کانفیگ اختصاصی V2Ray شما در عرض فقط {creation_time} توسط ربات ساخته شد . !**\n"
            "**#️⃣ کد سرویس(در ربات):** `{service_code}`\n"
            "**🔷 اسم کانفیگ:** `{account_name}`\n"
            "**📥 حجم انتخابی :** {volume}\n"
            "**⏰ مدت زمان :** {duration} روز\n"
            "**🔌 محدودیت کاربر :** {user_limit}\n\n"
            "**🌏 لینک سابسکریپشن آیپی‌ثابت + مولتی‌لوکیشن (یکجا) :**\n"
            "{subscription_url}\n\n"
            "{config_links_with_txt}\n\n"
            "💵 مبلغ `{amount_deducted}` تومان از موجودی **کیف‌ پول** شما کسر شد.\n"
            "💰 موجودی جدید **کیف‌ پول** شما:  `{new_balance}` تومان\n\n"
            "🚦جهت راهنمای اتصال اندروید/ویندوز/مک/آیفون/تلویزیون به بخش راهنمای ربات /help بروید."
        ),
        lang="fa",
    )
    txt = (
        txt_template.replace("{service_code}", str(code_service))
        .replace("{account_name}", username)
        .replace("{volume}", volume_text)
        .replace("{duration}", str(plan.duration))
        .replace("{user_limit}", ip_limit_text)
        .replace("{price}", f"{int(amount):,}")
        .replace("{subscription_url}", subscription_links_text)
        .replace("{config_links}", single_config_links_text)
        .replace("{config_links_with_txt}", single_config_links_section)
        .replace("{amount_deducted}", f"{int(amount):,}")
        .replace("{new_balance}", f"{new_amount:,}")
        .replace("{creation_time}", f"{creation_time_text} {creation_time_unit}")
    )
    discount_line = f"🎫 کد تخفیف: `{discount_code}`\n" if discount_code else ""
    log_title = "خرید جدید باکدتخفیف" if discount_code else " خرید جدید بدون کدتخفیف"
    log_text = (
        f"📢 **{log_title}**\n\n"
        f"👤 شناسه کاربر: `{user_id}`\n"
        f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
        f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
        f"🎫 کد سرویس: `{code_service}`\n"
        f"**🔷 اسم کانفیگ:** `{username}`\n"
        f"{discount_line}"
        f"📏 حجم خریداری شده: {volume_text}\n"
        f"**🔌 محدودیت کاربر :** {ip_limit_text}\n"
        f"💸 مبلغ پرداخت شده: `{int(amount):,}` تومان\n"
        f"💵 موجودی جدید کاربر: `{new_amount:,}` تومان\n."
        f"🔗 لینک کانفیگ:\n{subscription_links_text}"
    )

    if discount_code:
        await DiscountCodeManager().update_discount_usage(code=discount_code)

    try:
        user = await UserCRUD().read_user(user_id)
        if user and user.ref:
            await process_referral_reward_payout(user.ref, user_id)
    except Exception as e:
        logger.error("Error processing referral rewards: %s", e)

    await ServiceCRUD().create_service(
        code=code_service,
        username=username,
        enable=1,
        in_panel=panel.code,
        panel_userid=getattr(added_user, "id", None),
        id=user_id,
        package_size=gigabytes_to_bytes(float(gig)),
        createtime=Time_Date()["stamp"],
        expiration_time=day_to_timestamp(int(plan.duration)),
        data_limit_reset_strategy=plan.data_limit_reset_strategy
        if plan and hasattr(plan, "data_limit_reset_strategy")
        else "no_reset",
        ip_limit=plan.ip_limit if plan and hasattr(plan, "ip_limit") else 0,
        is_test=False,
    )
    await clear_user(user_id)
    await send_log_message(LogType.OTHER, message=log_text)
    await set_step(user_id, "home")
    purchase_buttons = ReplyInlineMarkup(
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
    short_caption = (
        f"**🎉 کانفیگ شما ساخته شد** (#{code_service})\n"
        f"**🔷 اسم کانفیگ:** `{username}`\n"
        f"🔗 `{primary_subscription_url}`"
    )
    if event is not None:
        await event.respond("✅", buttons=await bhome_buttons(user_id, lang))
        await respond_with_photo_and_text(
            event,
            file=qr_file,
            text=txt,
            short_caption=short_caption,
            buttons=purchase_buttons,
        )
    else:
        await Kenzo.send_message(user_id, "✅", buttons=await bhome_buttons(user_id, lang))
        await send_photo_and_text_to_user(
            Kenzo,
            user_id,
            file=qr_file,
            text=txt,
            short_caption=short_caption,
            buttons=purchase_buttons,
        )
    return True, ""


async def _complete_vpn_purchase(event, *, amount: int, discount_code: str | None = None) -> None:
    lang = await _user_lang(event.sender_id)
    gig, panel_code, plan = await _load_purchase_context(event.sender_id)
    if gig is None or panel_code is None or plan is None:
        await event.edit("خطا: اطلاعات مورد نیاز پیدا نشد.", buttons=await bhome_buttons(event.sender_id, lang))
        return

    is_sufficient, message = await check_user_balance(event.sender_id, amount)
    if not is_sufficient:
        volume_text = convert_storage(
            float(gig), getattr(plan, "plan_type", None), getattr(plan, "data_limit_reset_strategy", None)
        )
        if not message:
            message = await build_insufficient_balance_message(
                event.sender_id,
                amount,
                kind=KIND_VPN,
                product_label=getattr(plan, "name", None) or "کانفیگ VPN",
                volume=volume_text,
            )
        await event.delete()
        await event.respond("💸", buttons=await bhome_buttons(event.sender_id, "fa"))
        await event.respond(message, buttons=await create_balance_button(event.sender_id))
        return

    await create_vpn_purchase_for_user(
        event.sender_id,
        amount=amount,
        discount_code=discount_code,
        event=event,
    )

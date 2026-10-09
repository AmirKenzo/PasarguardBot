"""Callback handlers for user reseller purchase flow."""

from __future__ import annotations

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing.direct_pay_flow import create_balance_button, invoice_shortfall_notice
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    is_prepaid,
    requires_volume_input,
    validate_volume,
    volume_unit_label,
)
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.panels.admins import (
    admin_username_exists,
    get_reseller_admin,
    get_reseller_admin_user_count,
)
from app.services.panels.settings import panel_reseller_sale_enabled
from app.services.reseller.accounts import (
    ACTION_BUY_CAPACITY,
    ACTION_CHANGE_PASSWORD,
    ACTION_CREDENTIALS,
    ACTION_DELETE,
    ACTION_EXTRA_DAYS,
    ACTION_EXTRA_VOLUME,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_RESUME,
    ACTION_USAGE_CAP,
    ACTION_USAGE_REPORT,
    account_actions,
    delete_account,
    get_owned_account,
    is_admin_locked,
    pause_account,
    reset_password,
    resume_account,
)
from app.services.reseller.addons import ADDON_LOCK, ADDON_MAX_QUANTITY, buy_addon, quote_addon
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS, ADDON_VOLUME, addon_price
from app.services.reseller.purchase import reseller_sale_open
from app.services.reseller.usage_cap import parse_usage_cap_gb, set_reseller_usage_cap, usage_cap_menu_text
from app.telegram.keyboards import reseller as rs_buttons
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.reseller_plan_guides import (
    ADDON_NAMES,
    ADDON_TOKEN_OF,
    ADDON_TOKENS,
    ADDON_UNITS,
    addon_current_line,
    addon_preview_lines,
    buyer_plan_guide,
    load_guide_context,
    mode_name,
    parse_addon_quantity,
    toman,
)
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, delete_data, delete_data_many, get_data, get_step, set_data, set_step
from app.telegram.state.lock import acquire_user_lock, release_user_lock
from app.telegram.user.reseller.helpers import (
    _complete_reseller_purchase,
    _user_lang,
    apply_discount_amount,
    build_reseller_account_detail_text,
    build_reseller_confirm_text,
    build_reseller_renew_confirm_text,
    format_plan_button_text,
    generate_reseller_username,
    get_reseller_text,
    reseller_flow_edit,
    resolve_reseller_purchase_amount,
    show_account_credentials,
    show_account_detail,
    show_reseller_panel_picker,
    show_usage_history,
)
from app.telegram.user.reseller.keyboards import (
    build_addon_confirm_buttons,
    build_addon_preset_buttons,
    build_delete_confirm_buttons,
    build_my_reseller_account_buttons,
    build_my_resellers_list_buttons,
    build_password_confirm_buttons,
    build_reseller_confirm_buttons,
    build_reseller_plan_buttons,
    build_reseller_renew_confirm_buttons,
    build_usage_cap_menu_buttons,
    load_account_context,
)
from app.telegram.user.reseller.states import (
    ADDON_CODE_KEY,
    ADDON_QUANTITY_KEY,
    ADDON_TYPE_KEY,
    RESELLER_FLOW_MSG_KEY,
    STEP_ADDON_CONFIRM,
    STEP_ADDON_CUSTOM,
)
from app.telegram.user.start.helpers import fetch_welcome_text
from app.utils.formatting.dates import Time_Date

logger = get_logger(__name__)


async def _get_owned_account(event, code: int):
    acc = await get_owned_account(code, event.sender_id)
    if acc is None:
        await event.answer("یافت نشد.", alert=True)
    return acc


async def _reject_unless_allowed(event, account, action: str) -> bool:
    """Server-side guard matching the hidden button: a crafted callback can't bypass a disabled action."""
    panel, plan = await load_account_context(account)
    if action in account_actions(account, panel, plan):
        return False
    await event.answer("این عملیات برای این نمایندگی فعال نیست.", alert=True)
    return True


ADDON_ACTIONS = {ADDON_DAYS: ACTION_EXTRA_DAYS, ADDON_VOLUME: ACTION_EXTRA_VOLUME, ADDON_USERS: ACTION_BUY_CAPACITY}
_LEGACY_CAPACITY_KEYS = ("reseller_capacity_code", "reseller_capacity_quantity", "reseller_capacity_source")


async def _reseller_sale_enabled() -> bool:
    return await reseller_sale_open()


async def _show_reseller_panel_picker(event) -> None:
    await show_reseller_panel_picker(event)


async def _clear_reseller_discount(user_id: int) -> None:
    await delete_data(user_id, "reseller_discount_code")
    await delete_data(user_id, "reseller_discount_amount")
    await delete_data(user_id, "reseller_renew_discount_code")
    await delete_data(user_id, "reseller_renew_discount_amount")


async def _reject_if_admin_locked(event, account) -> bool:
    if not is_admin_locked(account):
        return False
    await event.answer(
        "این نمایندگی توسط ادمین غیرفعال شده و این عملیات مجاز نیست.",
        alert=True,
    )
    return True


async def _show_reseller_confirm(event):
    user_id = event.sender_id
    plan_id = await get_data(user_id, "reseller_plan_id")
    username = await get_data(user_id, "reseller_username")
    volume_raw = await get_data(user_id, "reseller_volume")
    plan = await ResellerPlanManager().get_plan(plan_id)
    volume = float(volume_raw) if volume_raw else None
    amount, discount_code = await resolve_reseller_purchase_amount(user_id, plan, volume)
    text = build_reseller_confirm_text(
        plan, username=username, volume=volume, amount=amount, discount_code=discount_code
    )
    show_discount = is_prepaid(plan) and not discount_code
    shortfall = await invoice_shortfall_notice(user_id, int(amount))
    if shortfall:
        text = f"{text}\n\n{shortfall}"
    await reseller_flow_edit(
        event,
        text,
        buttons=await build_reseller_confirm_buttons(show_discount=show_discount, topup=bool(shortfall)),
    )
    await set_step(user_id, "reseller_confirm")


async def _show_reseller_renew_confirm(event, account, plan):
    """Renewal review for the account's own plan: before → after, price, balance."""
    user_id = event.sender_id
    amount = calculate_purchase_price(plan)
    discount_code = await get_data(user_id, "reseller_renew_discount_code")
    discounted_raw = await get_data(user_id, "reseller_renew_discount_amount")
    if discount_code and discounted_raw is not None:
        try:
            amount = int(discounted_raw)
        except TypeError, ValueError:
            discount_code = None
    current_limit = int(account.data_limit or 0)
    used_traffic = 0
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if panel:
        try:
            admin = await get_reseller_admin(panel, account.panel_admin_id)
        except Exception as exc:
            logger.warning("renew preview could not read panel admin code=%s: %s", account.code, exc)
            admin = None
        if admin:
            current_limit = int(getattr(admin, "data_limit", 0) or 0)
            used_traffic = int(getattr(admin, "used_traffic", 0) or 0)
    user = await UserCRUD().read_user(user_id)
    text = build_reseller_renew_confirm_text(
        account,
        plan,
        amount=amount,
        discount_code=discount_code,
        current_limit=current_limit,
        used_traffic=used_traffic,
        now=Time_Date()["stamp"],
        balance=int(user.amount or 0) if user else None,
    )
    await reseller_flow_edit(
        event,
        text,
        buttons=await build_reseller_renew_confirm_buttons(account.code, plan.id, show_discount=not discount_code),
    )
    await set_data(user_id, "reseller_renew_plan_id", str(plan.id))
    await set_data(user_id, "reseller_renew_account_code", str(account.code))
    await set_step(user_id, "reseller_renew_confirm")


async def _own_renew_plan(event, account):
    """The account's own plan, the only one it renews with; answers the user when it is missing."""
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    if not plan or plan.pricing_mode != account.pricing_mode:
        await event.answer("پلن این نمایندگی پیدا نشد؛ برای تمدید با پشتیبانی تماس بگیرید.", alert=True)
        return None
    return plan


async def _clear_addon_state(user_id: int) -> None:
    await delete_data_many(user_id, (ADDON_CODE_KEY, ADDON_TYPE_KEY, ADDON_QUANTITY_KEY, *_LEGACY_CAPACITY_KEYS))


async def _load_addon_account(event, code: int, addon: str):
    """Owned account allowed to buy ``addon``, with its panel and plan; None after answering the user."""
    acc = await _get_owned_account(event, code)
    if not acc or await _reject_if_admin_locked(event, acc):
        return None
    panel, plan = await load_account_context(acc)
    if ADDON_ACTIONS[addon] not in account_actions(acc, panel, plan):
        await event.answer(f"{ADDON_NAMES[addon]} برای این نمایندگی فعال نیست.", alert=True)
        return None
    return acc, panel, plan


async def _show_addon_menu(event, acc, plan, addon: str) -> None:
    user_id = event.sender_id
    await _clear_addon_state(user_id)
    await set_step(user_id, "home")
    notes = {
        ADDON_DAYS: "روزها از تاریخ انقضای فعلی اضافه می‌شوند (اگر منقضی شده باشد از امروز) و پنل منقضی دوباره فعال می‌شود.",
        ADDON_VOLUME: "حجم روی حجم فعلی اضافه می‌شود و تا پایان مدت نمایندگی قابل استفاده است.",
        ADDON_USERS: "سقف یوزر به‌صورت دائمی بالا می‌رود و با تمدید یا تغییر پلن از بین نمی‌رود.",
    }
    text = (
        f"**🧩 {ADDON_NAMES[addon]} — `{acc.username}`**\n\n"
        f"{addon_current_line(acc, addon)}\n"
        f"💰 قیمت هر {ADDON_UNITS[addon]}: {toman(addon_price(plan, addon))}\n\n"
        f"ℹ️ {notes[addon]}\n\n"
        "مقدار را انتخاب کنید:"
    )
    await reseller_flow_edit(event, text, buttons=await build_addon_preset_buttons(acc.code, addon))


async def _show_addon_confirm(event, acc, plan, addon: str, quantity: int) -> None:
    user_id = event.sender_id
    quote, error = await quote_addon(acc, plan, addon, quantity)
    if error:
        if hasattr(event, "answer"):
            await event.answer(error, alert=True)
        else:
            await event.respond(error)
        return
    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    shortfall = max(quote.total - balance, 0)
    lines = [
        f"**🧾 تأیید خرید {ADDON_NAMES[addon]} — `{acc.username}`**",
        "",
        "**🔄 قبل ← بعد:**",
        *addon_preview_lines(quote, expired=acc.status == "expired"),
        "",
        f"➕ مقدار: {quote.quantity} {ADDON_UNITS[addon]}",
        f"💰 قیمت هر {ADDON_UNITS[addon]}: {toman(quote.unit_price)}",
        f"💵 مبلغ کل: {toman(quote.total)}",
        f"👛 موجودی فعلی: {toman(balance)}",
    ]
    if shortfall > 0:
        lines.append(f"⚠️ مبلغ موردنیاز برای تکمیل خرید: {toman(shortfall)}")
    await set_data(user_id, ADDON_CODE_KEY, str(acc.code))
    await set_data(user_id, ADDON_TYPE_KEY, addon)
    await set_data(user_id, ADDON_QUANTITY_KEY, str(quote.quantity))
    await reseller_flow_edit(
        event,
        "\n".join(lines),
        buttons=await build_addon_confirm_buttons(acc.code, addon, topup=shortfall > 0),
    )
    await set_step(user_id, STEP_ADDON_CONFIRM)


async def _prompt_addon_custom(event, acc, addon: str) -> None:
    user_id = event.sender_id
    await set_data(user_id, ADDON_CODE_KEY, str(acc.code))
    await set_data(user_id, ADDON_TYPE_KEY, addon)
    await set_step(user_id, STEP_ADDON_CUSTOM)
    await reseller_flow_edit(
        event,
        f"**🔢 {ADDON_NAMES[addon]} دلخواه — `{acc.username}`**\n\n"
        f"تعداد {ADDON_UNITS[addon]} را به عدد ارسال کنید (حداکثر {ADDON_MAX_QUANTITY[addon]:,}):",
        buttons=[[await rs_buttons.rs_addon_back_button(acc.code, ADDON_TOKEN_OF[addon])]],
    )


async def _buy_addon_confirmed(event, code: int, addon: str) -> None:
    user_id = event.sender_id
    if await get_step(user_id) != STEP_ADDON_CONFIRM:
        await event.answer("نشست منقضی شده.", alert=True)
        return
    stored_code = await get_data(user_id, ADDON_CODE_KEY)
    stored_addon = await get_data(user_id, ADDON_TYPE_KEY)
    quantity_raw = await get_data(user_id, ADDON_QUANTITY_KEY)
    if stored_code != str(code) or stored_addon != addon or not quantity_raw:
        await event.answer("نشست منقضی شده.", alert=True)
        return
    loaded = await _load_addon_account(event, code, addon)
    if not loaded:
        return
    acc, panel, plan = loaded

    if not await acquire_user_lock(user_id, ADDON_LOCK, ttl=20):
        await event.answer("درخواست قبلی در حال پردازش است.", alert=True)
        return
    try:
        success, msg, _quote = await buy_addon(
            acc, panel, plan, addon, int(quantity_raw), telegram_id=user_id, actor_id=user_id, source="bot"
        )
    finally:
        await release_user_lock(user_id, ADDON_LOCK)

    await _clear_addon_state(user_id)
    await set_step(user_id, "home")
    if not success and msg.startswith("موجودی کافی نیست"):
        await event.delete()
        await event.respond(msg, buttons=await create_balance_button(user_id))
        return
    await event.answer(msg, alert=True)
    ok, acc = await ResellerAccountCRUD().get_account(code)
    if ok:
        await show_account_detail(event, acc)


async def _show_plan_guide(event, plan) -> None:
    """Plan card before purchase: what it includes and how it works."""
    user_id = event.sender_id
    text = buyer_plan_guide(plan, await load_guide_context(), title=f"🏢 {format_plan_button_text(plan)}")
    await reseller_flow_edit(
        event,
        text,
        buttons=[
            [Button.inline("✅ ادامه خرید این پلن", data=f"ResellerBuy_go:{plan.id}")],
            [await rs_buttons.rs_buy_back_button(f"ResellerPanel_{plan.panel_code}")],
            [await rs_buttons.rs_buy_cancel_button()],
        ],
    )
    await set_step(user_id, "reseller_select_plan")


@bot_is_offline
async def reseller_buy_callback(event: events.CallbackQuery.Event):
    if not event.is_private:
        return
    data = event.data.decode("utf-8")

    if (
        not await _reseller_sale_enabled()
        and not data.startswith("ResellerMy")
        and not data.startswith("ResellerAccount_")
    ):
        await event.answer("⛔️ فروش توسط ادمین بسته است.", alert=True)
        return

    user_id = event.sender_id

    if data == "ResellerBuy_cancel":
        await _clear_reseller_discount(user_id)
        await clear_user(user_id)
        lang = await _user_lang(user_id)
        txt = await fetch_welcome_text(lang)
        await set_step(user_id, "home")
        await event.delete()
        await event.respond(txt, buttons=await bhome_buttons(user_id, lang))
        return

    if data in ("ResellerBuy_start", "ResellerBuy_back_panels"):
        await _clear_reseller_discount(user_id)
        step = (await get_step(user_id)) or ""
        if step == "panel" or step.startswith("reseller_plan_"):
            await set_step(user_id, "home")
        await delete_data(user_id, RESELLER_FLOW_MSG_KEY)
        await _show_reseller_panel_picker(event)
        return

    if data.startswith("ResellerPanel_"):
        panel_code = int(data.split("_")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel or not panel_reseller_sale_enabled(panel):
            await event.answer("این پنل برای فروش نمایندگی فعال نیست.", alert=True)
            return
        plans = await ResellerPlanManager().get_all_plans(panel_code=panel_code, enabled_only=True)
        if not plans:
            await event.answer("پلنی برای این پنل نیست.", alert=True)
            return
        await set_data(user_id, "reseller_panel_code", str(panel_code))
        panel_name = panel.name
        prompt = await get_reseller_text(
            "reseller_select_plan_prompt",
            f"**پنل {panel_name}**\n\nپلن نمایندگی را انتخاب کنید:",
            user_id,
            panel_name=panel_name,
        )
        plan_lines = "\n".join(f"🔹 {format_plan_button_text(p)} — {mode_name(p.pricing_mode)}" for p in plans)
        await reseller_flow_edit(
            event,
            f"{prompt}\n\n{plan_lines}\n\nبا انتخاب هر پلن، راهنمای کامل آن نمایش داده می‌شود.",
            buttons=await build_reseller_plan_buttons(plans),
        )
        await set_step(user_id, "reseller_select_plan")
        return

    if data.startswith("ResellerPlan_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan or not plan.enable:
            await event.answer("پلن یافت نشد.", alert=True)
            return
        await _show_plan_guide(event, plan)
        return

    if data.startswith("ResellerBuy_go:"):
        plan_id = int(data.split(":")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan or not plan.enable:
            await event.answer("پلن یافت نشد.", alert=True)
            return
        plan_panel = await PanelsManager().get_panel_by_code(code=plan.panel_code)
        if not plan_panel or not panel_reseller_sale_enabled(plan_panel):
            await event.answer("این پنل برای فروش نمایندگی فعال نیست.", alert=True)
            return
        await _clear_reseller_discount(user_id)
        await set_data(user_id, "reseller_plan_id", str(plan_id))
        await set_data(user_id, "reseller_panel_code", str(plan.panel_code))
        if requires_volume_input(plan):
            unit = volume_unit_label(plan.pricing_mode)
            await reseller_flow_edit(
                event,
                f"**{mode_name(plan.pricing_mode)}**\n\n"
                f"حجم را به {unit} وارد کنید"
                f"{f' (حداقل {plan.min_volume:g} — حداکثر {plan.max_volume:g})' if plan.max_volume else ''}:",
                buttons=[[Button.inline("🔙 بازگشت", data="ResellerBuy_back_panels")]],
            )
            await set_step(user_id, "reseller_enter_volume")
            return
        await _prompt_reseller_username(event, plan)
        return

    if data == "ResellerBuy_back_username":
        plan_id = await get_data(user_id, "reseller_plan_id")
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            await _prompt_reseller_username(event, plan)
        return

    if data == "ResellerBuy_apply_discount":
        if await get_step(user_id) != "reseller_confirm":
            await event.answer("نشست منقضی شده.", alert=True)
            return
        plan_id = await get_data(user_id, "reseller_plan_id")
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan or not is_prepaid(plan):
            await event.answer("کد تخفیف فقط برای پلن ثابت و نامحدود است.", alert=True)
            return
        await reseller_flow_edit(
            event,
            "**🎟 کد تخفیف خود را ارسال کنید:**",
            buttons=[[await rs_buttons.rs_buy_back_button("ResellerBuy_back_confirm")]],
        )
        await set_step(user_id, "reseller_discount_code")
        return

    if data == "ResellerBuy_back_confirm":
        await _show_reseller_confirm(event)
        return

    if data == "ResellerBuy_confirm":
        if await get_step(user_id) != "reseller_confirm":
            await event.answer("نشست منقضی شده.", alert=True)
            return
        plan_id = await get_data(user_id, "reseller_plan_id")
        plan = await ResellerPlanManager().get_plan(plan_id)
        volume_raw = await get_data(user_id, "reseller_volume")
        volume = float(volume_raw) if volume_raw else None
        amount, discount_code = await resolve_reseller_purchase_amount(user_id, plan, volume)
        await _complete_reseller_purchase(event, amount=amount, discount_code=discount_code)
        return

    if data == "ResellerBuy_random_username":
        username = generate_reseller_username()
        await set_data(user_id, "reseller_username", username)
        await _show_reseller_confirm(event)
        return

    if data == "ResellerMy_list" or data == "ResellerMy_open":
        accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
        if not accounts:
            await event.edit(
                await get_reseller_text(
                    "reseller_my_list_empty",
                    "**📋 نمایندگی‌های من**\n\nشما نمایندگی فعالی ندارید.",
                    user_id,
                ),
                buttons=[[Button.inline("🏢 خرید پنل نمایندگی", data="ResellerBuy_start")]]
                if await _reseller_sale_enabled()
                else None,
            )
            return
        await event.edit(
            await get_reseller_text(
                "reseller_my_list_intro",
                f"**📋 نمایندگی‌های من** ({len(accounts)} مورد)\n\nیک نمایندگی را انتخاب کنید:",
                user_id,
                count=str(len(accounts)),
            ),
            buttons=await build_my_resellers_list_buttons(accounts),
        )
        return

    if data.startswith("ResellerAccount_view:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        # Back from a typed-value prompt: stop waiting for its input.
        if await get_step(user_id) in (STEP_ADDON_CUSTOM, STEP_ADDON_CONFIRM, "reseller_capacity_custom_input"):
            await _clear_addon_state(user_id)
            await set_step(user_id, "home")
        await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_pause:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_PAUSE):
            return
        ok, msg = await pause_account(acc)
        await event.answer(msg, alert=True)
        if ok:
            ok, acc = await ResellerAccountCRUD().get_account(code)
            if ok:
                await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_resume:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_RESUME):
            return
        ok, msg = await resume_account(acc)
        await event.answer(msg, alert=True)
        if ok:
            ok, acc = await ResellerAccountCRUD().get_account(code)
            if ok:
                await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_usage:"):
        parts = data.split(":")
        code = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        # Usage and hourly plans both have a charge history; the action decides who sees it.
        if await _reject_unless_allowed(event, acc, ACTION_USAGE_REPORT):
            return
        await show_usage_history(event, acc, page=page)
        return

    if data.startswith("ResellerAccount_usage_cap:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        if acc.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return
        if await _reject_unless_allowed(event, acc, ACTION_USAGE_CAP):
            return
        await delete_data(event.sender_id, "reseller_usage_cap_code")
        await set_step(event.sender_id, "home")
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        used = 0
        if panel:
            try:
                admin = await get_reseller_admin(panel, acc.panel_admin_id)
                used = int(getattr(admin, "used_traffic", 0) or 0) if admin else 0
            except Exception:
                used = 0
        await event.edit(
            usage_cap_menu_text(acc, used_bytes=used),
            buttons=await build_usage_cap_menu_buttons(code, has_cap=bool(acc.usage_cap_bytes)),
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerAccount_usage_cap_set:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        if acc.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return
        if await _reject_unless_allowed(event, acc, ACTION_USAGE_CAP):
            return
        await set_data(event.sender_id, "reseller_usage_cap_code", str(code))
        await set_step(event.sender_id, "reseller_usage_cap_input")
        await event.edit(
            f"**📦 تنظیم سقف مصرف — `{acc.username}`**\n\n"
            "مقدار سقف را به **گیگابایت** ارسال کنید.\n"
            "مثال: `50`\n\n"
            "برای حذف محدودیت عدد `0` بفرستید.",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerAccount_usage_cap:{code}")]],
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerAccount_usage_cap_clear:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        if acc.pricing_mode != "usage":
            await event.answer("سقف مصرف فقط برای پلن مصرفی است.", alert=True)
            return
        if await _reject_unless_allowed(event, acc, ACTION_USAGE_CAP):
            return
        ok, msg = await set_reseller_usage_cap(acc, gigabytes=None, actor_id=event.sender_id)
        await event.answer(msg, alert=True)
        if ok:
            ok, acc = await ResellerAccountCRUD().get_account(code)
            if ok:
                await show_account_detail(event, acc)
        return

    if data.startswith(("ResellerAccount_addon:", "ResellerAccount_capacity:")):
        parts = data.split(":")
        code = int(parts[1])
        addon = ADDON_TOKENS.get(parts[2]) if len(parts) > 2 else ADDON_USERS
        if not addon:
            await event.answer("درخواست نامعتبر است.", alert=True)
            return
        loaded = await _load_addon_account(event, code, addon)
        if not loaded:
            return
        acc, _panel, plan = loaded
        await _show_addon_menu(event, acc, plan, addon)
        return

    if data.startswith(("ResellerAccount_addon_amount:", "ResellerAccount_capacity_amount:")):
        parts = data.split(":")
        code = int(parts[1])
        if data.startswith("ResellerAccount_capacity_amount:"):
            addon, quantity_raw = ADDON_USERS, parts[2]
        else:
            addon, quantity_raw = ADDON_TOKENS.get(parts[2]), parts[3] if len(parts) > 3 else ""
        quantity, error = parse_addon_quantity(addon, quantity_raw) if addon else (None, "درخواست نامعتبر است.")
        if error:
            await event.answer(error, alert=True)
            return
        loaded = await _load_addon_account(event, code, addon)
        if not loaded:
            return
        acc, _panel, plan = loaded
        await _show_addon_confirm(event, acc, plan, addon, quantity)
        return

    if data.startswith(("ResellerAccount_addon_custom:", "ResellerAccount_capacity_custom:")):
        parts = data.split(":")
        code = int(parts[1])
        addon = ADDON_TOKENS.get(parts[2]) if len(parts) > 2 else ADDON_USERS
        if not addon:
            await event.answer("درخواست نامعتبر است.", alert=True)
            return
        loaded = await _load_addon_account(event, code, addon)
        if not loaded:
            return
        await _prompt_addon_custom(event, loaded[0], addon)
        return

    if data.startswith(("ResellerAccount_addon_confirm:", "ResellerAccount_capacity_confirm:")):
        parts = data.split(":")
        code = int(parts[1])
        addon = ADDON_TOKENS.get(parts[2]) if len(parts) > 2 else ADDON_USERS
        if not addon:
            await event.answer("درخواست نامعتبر است.", alert=True)
            return
        await _buy_addon_confirmed(event, code, addon)
        return

    if data.startswith("ResellerAccount_capacity_cancel:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        await _clear_addon_state(user_id)
        await set_step(user_id, "home")
        if acc:
            await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_delete:") and not data.startswith("ResellerAccount_delete_confirm:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc or await _reject_unless_allowed(event, acc, ACTION_DELETE):
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        sub_users = 0
        if panel:
            try:
                sub_users = await get_reseller_admin_user_count(panel, acc.panel_admin_id)
            except Exception:
                sub_users = 0
        await event.edit(
            f"**⚠️ حذف کامل نمایندگی `{acc.username}`**\n\n"
            f"• ادمین پنل حذف می‌شود\n"
            f"• `{sub_users}` یوزر وابسته حذف می‌شوند\n"
            f"• این عمل غیرقابل بازگشت است\n\n"
            "آیا مطمئن هستید؟",
            buttons=await build_delete_confirm_buttons(code),
        )
        return

    if data.startswith("ResellerAccount_delete_confirm:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc or await _reject_unless_allowed(event, acc, ACTION_DELETE):
            return
        ok, msg = await delete_account(acc)
        await event.answer(msg, alert=True)
        if ok:
            accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
            if accounts:
                await event.edit(
                    f"**📋 نمایندگی‌های من** ({len(accounts)} مورد)\n\nیک نمایندگی را انتخاب کنید:",
                    buttons=await build_my_resellers_list_buttons(accounts),
                )
            else:
                await event.edit(
                    "**📋 نمایندگی‌های من**\n\nشما نمایندگی فعالی ندارید.",
                    buttons=[[Button.inline("🏢 خرید پنل نمایندگی", data="ResellerBuy_start")]]
                    if await _reseller_sale_enabled()
                    else None,
                )
        return

    if data.startswith("ResellerAccount_creds:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_CREDENTIALS):
            return
        await show_account_credentials(event, acc)
        return

    if data.startswith("ResellerAccount_chpwd:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(
            event, acc, ACTION_CHANGE_PASSWORD
        ):
            return
        await event.edit(
            f"**⚠️ تغییر رمز `{acc.username}`**\n\nرمز فعلی پنل غیرفعال می‌شود و رمز جدید ساخته می‌شود.\nآیا مطمئن هستید؟",
            buttons=await build_password_confirm_buttons(code),
        )
        return

    if data.startswith("ResellerAccount_chpwd_confirm:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(
            event, acc, ACTION_CHANGE_PASSWORD
        ):
            return
        ok, msg, _ = await reset_password(acc, actor_id=event.sender_id)
        if not ok:
            await event.answer(msg, alert=True)
            return
        ok, acc = await ResellerAccountCRUD().get_account(code)
        if ok:
            await show_account_credentials(event, acc)
        await event.answer(msg, alert=False)
        return

    if data.startswith("ResellerAccount_status:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_renew_plan:"):
        parts = data.split(":")
        code = int(parts[1])
        plan_id = int(parts[2])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_RENEW):
            return
        plan = await _own_renew_plan(event, acc)
        if not plan:
            return
        if plan_id != plan.id:
            await event.answer("تمدید فقط با همان پلن خریداری‌شده امکان‌پذیر است.", alert=True)
            return
        await delete_data(user_id, "reseller_renew_discount_code")
        await delete_data(user_id, "reseller_renew_discount_amount")
        await _show_reseller_renew_confirm(event, acc, plan)
        return

    if data.startswith("ResellerAccount_renew_discount:"):
        parts = data.split(":")
        code = int(parts[1])
        plan_id = int(parts[2])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_RENEW):
            return
        if plan_id != int(acc.plan_id or 0):
            await event.answer("تمدید فقط با همان پلن خریداری‌شده امکان‌پذیر است.", alert=True)
            return
        await set_data(user_id, "reseller_renew_account_code", str(code))
        await set_data(user_id, "reseller_renew_plan_id", str(plan_id))
        await reseller_flow_edit(
            event,
            "**🎟 کد تخفیف تمدید را ارسال کنید:**",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerAccount_renew_plan:{code}:{plan_id}")]],
        )
        await set_step(user_id, "reseller_renew_discount_code")
        return

    if data.startswith("ResellerAccount_renew_confirm:"):
        parts = data.split(":")
        code = int(parts[1])
        plan_id = int(parts[2])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_RENEW):
            return
        plan = await _own_renew_plan(event, acc)
        if not plan:
            return
        if plan_id != plan.id:
            await event.answer("تمدید فقط با همان پلن خریداری‌شده امکان‌پذیر است.", alert=True)
            return
        if (
            await get_step(user_id) != "reseller_renew_confirm"
            or await get_data(user_id, "reseller_renew_account_code") != str(code)
            or await get_data(user_id, "reseller_renew_plan_id") != str(plan.id)
        ):
            await event.answer("نشست منقضی شده؛ دوباره تمدید را باز کنید.", alert=True)
            return
        # The price is computed on the server from the plan and the code's percentage.
        discount_code = await get_data(user_id, "reseller_renew_discount_code") or None
        if not await acquire_user_lock(user_id, "reseller_renew", ttl=30):
            await event.answer("درخواست قبلی در حال پردازش است.", alert=True)
            return
        try:
            success, msg = await renew_reseller_account(code, plan.id, user_id, discount_code=discount_code)
        finally:
            await release_user_lock(user_id, "reseller_renew")
        await delete_data(user_id, "reseller_renew_discount_code")
        await delete_data(user_id, "reseller_renew_discount_amount")
        await delete_data(user_id, "reseller_renew_plan_id")
        await delete_data(user_id, "reseller_renew_account_code")
        await set_step(user_id, "home")
        if not success and msg.startswith("موجودی کافی نیست"):
            await event.delete()
            await event.respond(msg, buttons=await create_balance_button(user_id))
            return
        await event.answer(msg, alert=True)
        if success:
            ok, acc = await ResellerAccountCRUD().get_account(code)
            if ok:
                await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_renew:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc) or await _reject_unless_allowed(event, acc, ACTION_RENEW):
            return
        plan = await _own_renew_plan(event, acc)
        if not plan:
            return
        await delete_data(user_id, "reseller_renew_discount_code")
        await delete_data(user_id, "reseller_renew_discount_amount")
        await _show_reseller_renew_confirm(event, acc, plan)
        return


async def _prompt_reseller_username(event, plan):
    user_id = event.sender_id
    await reseller_flow_edit(
        event,
        "**👤 نام کاربری ادمین پنل**\n\nنام کاربری دلخواه را ارسال کنید یا از دکمه زیر استفاده کنید:",
        buttons=[
            [await rs_buttons.rs_buy_random_username_button()],
            [await rs_buttons.rs_buy_back_button(f"ResellerPlan_{plan.id}")],
        ],
    )
    await set_step(user_id, "reseller_enter_username")


async def reseller_volume_message_filter(event: Message) -> bool:
    return (
        event.is_private and bool(event.message.message) and await get_step(event.sender_id) == "reseller_enter_volume"
    )


async def reseller_username_message_filter(event: Message) -> bool:
    return (
        event.is_private
        and bool(event.message.message)
        and await get_step(event.sender_id) == "reseller_enter_username"
    )


async def reseller_discount_message_filter(event: Message) -> bool:
    return (
        event.is_private and bool(event.message.message) and await get_step(event.sender_id) == "reseller_discount_code"
    )


async def reseller_renew_discount_message_filter(event: Message) -> bool:
    return (
        event.is_private
        and bool(event.message.message)
        and await get_step(event.sender_id) == "reseller_renew_discount_code"
    )


@bot_is_offline
async def reseller_volume_message(event: Message):
    if not await _reseller_sale_enabled():
        return
    user_id = event.sender_id
    plan_id = await get_data(user_id, "reseller_plan_id")
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan:
        return
    try:
        volume = float(event.message.message.strip().replace(",", ""))
    except ValueError:
        await event.respond("فقط عدد وارد کنید.")
        return
    ok, err = validate_volume(plan, volume)
    if not ok:
        await event.respond(err)
        return
    await set_data(user_id, "reseller_volume", str(volume))
    with contextlib.suppress(Exception):
        await event.delete()
    await _prompt_reseller_username(event, plan)


@bot_is_offline
async def reseller_username_message(event: Message):
    if not await _reseller_sale_enabled():
        return
    user_id = event.sender_id
    username = (event.message.message or "").strip()
    if len(username) < 3:
        await event.respond("نام کاربری حداقل ۳ کاراکتر باشد.")
        return
    panel_code = await get_data(user_id, "reseller_panel_code")
    panel = await PanelsManager().get_panel_by_code(code=int(panel_code))
    if panel and await admin_username_exists(panel, username):
        await event.respond("این نام در پنل وجود دارد. نام دیگری انتخاب کنید.")
        return
    await set_data(user_id, "reseller_username", username)
    with contextlib.suppress(Exception):
        await event.delete()
    await _show_reseller_confirm(event)


@bot_is_offline
async def reseller_discount_message(event: Message):
    if not await _reseller_sale_enabled():
        return
    user_id = event.sender_id
    code = (event.message.message or "").strip().upper()
    status, result = await DiscountCodeManager().validate_discount_code(code=code, user_id=user_id)
    with contextlib.suppress(Exception):
        await event.delete()
    if not status:
        await event.respond(str(result))
        return
    plan_id = await get_data(user_id, "reseller_plan_id")
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not is_prepaid(plan):
        await event.respond("کد تخفیف فقط برای پلن ثابت و نامحدود است.")
        return
    volume_raw = await get_data(user_id, "reseller_volume")
    volume = float(volume_raw) if volume_raw else None
    base = calculate_purchase_price(plan, volume)
    discounted = apply_discount_amount(base, result.discount_percentage)
    await set_data(user_id, "reseller_discount_code", result.code)
    await set_data(user_id, "reseller_discount_amount", str(discounted))
    await _show_reseller_confirm(event)


@bot_is_offline
async def reseller_renew_discount_message(event: Message):
    user_id = event.sender_id
    code = (event.message.message or "").strip().upper()
    status, result = await DiscountCodeManager().validate_discount_code(code=code, user_id=user_id)
    with contextlib.suppress(Exception):
        await event.delete()
    if not status:
        await event.respond(str(result))
        return
    plan_id = await get_data(user_id, "reseller_renew_plan_id")
    account_code = await get_data(user_id, "reseller_renew_account_code")
    plan = await ResellerPlanManager().get_plan(plan_id)
    acc = await get_owned_account(account_code, user_id) if account_code else None
    if not plan or not acc or int(acc.plan_id or 0) != plan.id:
        await set_step(user_id, "home")
        await event.respond("نشست تمدید منقضی شده. دوباره تلاش کنید.")
        return
    base = calculate_purchase_price(plan)
    discounted = apply_discount_amount(base, result.discount_percentage)
    await set_data(user_id, "reseller_renew_discount_code", result.code)
    await set_data(user_id, "reseller_renew_discount_amount", str(discounted))
    await _show_reseller_renew_confirm(event, acc, plan)


async def reseller_usage_cap_message_filter(event: Message) -> bool:
    return (
        event.is_private
        and bool(event.message.message)
        and await get_step(event.sender_id) == "reseller_usage_cap_input"
    )


@bot_is_offline
async def reseller_usage_cap_message(event: Message):
    user_id = event.sender_id
    code_raw = await get_data(user_id, "reseller_usage_cap_code")
    if not code_raw:
        await set_step(user_id, "home")
        return
    ok, acc = await ResellerAccountCRUD().get_account(int(code_raw))
    if not ok or acc.telegram_id != user_id:
        await set_step(user_id, "home")
        await delete_data(user_id, "reseller_usage_cap_code")
        await event.respond("نمایندگی یافت نشد.")
        return
    if is_admin_locked(acc):
        await set_step(user_id, "home")
        await delete_data(user_id, "reseller_usage_cap_code")
        await event.respond("این نمایندگی توسط ادمین غیرفعال شده است.")
        return
    if acc.pricing_mode != "usage":
        await set_step(user_id, "home")
        await delete_data(user_id, "reseller_usage_cap_code")
        await event.respond("سقف مصرف فقط برای پلن مصرفی است.")
        return

    gb = parse_usage_cap_gb(event.message.message)
    if gb is None:
        await event.respond("فقط عدد معتبر (گیگابایت) وارد کنید. مثال: `50` یا `0` برای حذف.")
        return

    success, msg = await set_reseller_usage_cap(
        acc,
        gigabytes=None if gb <= 0 else gb,
        actor_id=user_id,
    )
    await delete_data(user_id, "reseller_usage_cap_code")
    await set_step(user_id, "home")
    await event.respond(msg)
    if success:
        ok, acc = await ResellerAccountCRUD().get_account(int(code_raw))
        if ok:
            text = await build_reseller_account_detail_text(acc, show_password=False)
            await event.respond(text, buttons=await build_my_reseller_account_buttons(acc))


async def reseller_capacity_custom_message_filter(event: Message) -> bool:
    return (
        event.is_private
        and bool(event.message.message)
        and await get_step(event.sender_id) in (STEP_ADDON_CUSTOM, "reseller_capacity_custom_input")
    )


@bot_is_offline
async def reseller_capacity_custom_message(event: Message):
    """Typed add-on quantity (extra days, GB or users); the old capacity step maps to extra users."""
    user_id = event.sender_id
    step = await get_step(user_id)
    code_raw = await get_data(user_id, ADDON_CODE_KEY) or await get_data(user_id, "reseller_capacity_code")
    addon = await get_data(user_id, ADDON_TYPE_KEY) if step == STEP_ADDON_CUSTOM else ADDON_USERS
    if not code_raw or addon not in ADDON_ACTIONS:
        await _clear_addon_state(user_id)
        await set_step(user_id, "home")
        return
    acc = await get_owned_account(code_raw, user_id)
    if not acc:
        await _clear_addon_state(user_id)
        await set_step(user_id, "home")
        await event.respond("نمایندگی یافت نشد.")
        return
    if is_admin_locked(acc):
        await _clear_addon_state(user_id)
        await set_step(user_id, "home")
        await event.respond("این نمایندگی توسط ادمین غیرفعال شده است.")
        return
    panel, plan = await load_account_context(acc)
    if ADDON_ACTIONS[addon] not in account_actions(acc, panel, plan):
        await _clear_addon_state(user_id)
        await set_step(user_id, "home")
        await event.respond(f"{ADDON_NAMES[addon]} برای این نمایندگی فعال نیست.")
        return

    quantity, error = parse_addon_quantity(addon, event.message.message)
    if error:
        await event.respond(await get_reseller_text("reseller_capacity_invalid_amount", error, user_id))
        return

    with contextlib.suppress(Exception):
        await event.delete()
    await _show_addon_confirm(event, acc, plan, addon, quantity)


def register(client):
    client.add_event_handler(
        reseller_buy_callback,
        events.CallbackQuery(pattern=rb"^Reseller(Buy|Panel|Plan|My|Account)_"),
    )
    client.add_event_handler(
        reseller_volume_message,
        events.NewMessage(incoming=True, func=reseller_volume_message_filter),
    )
    client.add_event_handler(
        reseller_username_message,
        events.NewMessage(incoming=True, func=reseller_username_message_filter),
    )
    client.add_event_handler(
        reseller_discount_message,
        events.NewMessage(incoming=True, func=reseller_discount_message_filter),
    )
    client.add_event_handler(
        reseller_renew_discount_message,
        events.NewMessage(incoming=True, func=reseller_renew_discount_message_filter),
    )
    client.add_event_handler(
        reseller_usage_cap_message,
        events.NewMessage(incoming=True, func=reseller_usage_cap_message_filter),
    )
    client.add_event_handler(
        reseller_capacity_custom_message,
        events.NewMessage(incoming=True, func=reseller_capacity_custom_message_filter),
    )

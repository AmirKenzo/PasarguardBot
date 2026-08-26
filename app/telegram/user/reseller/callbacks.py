"""Callback handlers for user reseller purchase flow."""

from __future__ import annotations

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing.direct_pay_flow import create_balance_button
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    pricing_mode_label,
    requires_volume_input,
    validate_volume,
    volume_unit_label,
)
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.panels.admins import (
    admin_username_exists,
    get_reseller_admin,
    get_reseller_admin_user_count,
    reset_reseller_admin_password,
)
from app.services.panels.settings import (
    panel_reseller_capacity_enabled,
    panel_reseller_capacity_settings,
    panel_reseller_sale_enabled,
)
from app.services.reseller.capacity import (
    CAPACITY_CUSTOM_MAX,
    calculate_capacity_price,
    increase_reseller_capacity,
    validate_capacity_quantity,
)
from app.services.reseller.logging import send_reseller_log
from app.services.reseller.usage_cap import parse_usage_cap_gb, set_reseller_usage_cap, usage_cap_menu_text
from app.telegram.keyboards import reseller as rs_buttons
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, delete_data, get_data, get_step, set_data, set_step
from app.telegram.state.lock import acquire_user_lock, release_user_lock
from app.telegram.user.reseller.helpers import (
    _complete_reseller_purchase,
    _user_lang,
    apply_discount_amount,
    build_reseller_account_detail_text,
    build_reseller_confirm_text,
    build_reseller_renew_confirm_text,
    delete_reseller_account,
    generate_reseller_username,
    get_reseller_text,
    is_admin_locked,
    pause_reseller_account,
    reseller_flow_edit,
    resolve_reseller_purchase_amount,
    resume_reseller_account,
    show_account_credentials,
    show_account_detail,
    show_reseller_panel_picker,
    show_usage_history,
)
from app.telegram.user.reseller.keyboards import (
    build_capacity_confirm_buttons,
    build_capacity_preset_buttons,
    build_delete_confirm_buttons,
    build_my_reseller_account_buttons,
    build_my_resellers_list_buttons,
    build_password_confirm_buttons,
    build_reseller_confirm_buttons,
    build_reseller_plan_buttons,
    build_reseller_renew_confirm_buttons,
    build_reseller_renew_plan_buttons,
    build_usage_cap_menu_buttons,
)
from app.telegram.user.reseller.states import RESELLER_FLOW_MSG_KEY
from app.telegram.user.start.helpers import DEFAULT_START_MESSAGE
from app.utils.security.crypto import encrypt_data
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def _get_owned_account(event, code: int):
    ok, acc = await ResellerAccountCRUD().get_account(code)
    if not ok or acc.telegram_id != event.sender_id:
        await event.answer("یافت نشد.", alert=True)
        return None
    return acc


async def _reseller_sale_enabled() -> bool:
    settings = await SettingsManager().get_settings()
    return bool(settings and settings.sale_mode and settings.reseller_sale_mode)


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
    show_discount = plan.pricing_mode == "fixed" and not discount_code
    await reseller_flow_edit(
        event,
        text,
        buttons=await build_reseller_confirm_buttons(show_discount=show_discount),
    )
    await set_step(user_id, "reseller_confirm")


async def _show_reseller_renew_confirm(event, account, plan):
    user_id = event.sender_id
    amount = calculate_purchase_price(plan)
    discount_code = await get_data(user_id, "reseller_renew_discount_code")
    discounted_raw = await get_data(user_id, "reseller_renew_discount_amount")
    if discount_code and discounted_raw is not None:
        with contextlib.suppress(TypeError, ValueError):
            amount = int(discounted_raw)
    text = build_reseller_renew_confirm_text(plan, amount=amount, discount_code=discount_code)
    await reseller_flow_edit(
        event,
        text,
        buttons=await build_reseller_renew_confirm_buttons(account.code, plan.id),
    )
    await set_data(user_id, "reseller_renew_plan_id", str(plan.id))
    await set_data(user_id, "reseller_renew_account_code", str(account.code))
    await set_step(user_id, "reseller_renew_confirm")


async def _clear_capacity_state(user_id: int) -> None:
    await delete_data(user_id, "reseller_capacity_code")
    await delete_data(user_id, "reseller_capacity_quantity")
    await delete_data(user_id, "reseller_capacity_source")


async def _show_capacity_confirm(event, account, panel, quantity: int, *, source: str) -> None:
    user_id = event.sender_id
    price_per_user = int(panel_reseller_capacity_settings(panel)["price_per_user"])
    total_amount = calculate_capacity_price(panel, quantity, price_per_user=price_per_user)
    limit_before = int(account.max_users or 0)
    limit_after = limit_before + quantity

    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    shortfall = max(total_amount - balance, 0)

    lines = [
        f"**🧾 تأیید خرید ظرفیت کاربر — `{account.username}`**\n",
        f"👥 User Limit فعلی: {limit_before}",
        f"➕ تعداد درخواستی: {quantity}",
        f"📊 User Limit جدید: {limit_after}",
        f"💰 قیمت هر کاربر: {price_per_user:,} تومان",
        f"💵 مبلغ کل: {total_amount:,} تومان",
        f"👛 موجودی فعلی: {balance:,} تومان",
    ]
    if shortfall > 0:
        lines.append(f"⚠️ مبلغ موردنیاز برای تکمیل خرید: {shortfall:,} تومان")
    text = await get_reseller_text(
        "reseller_capacity_confirm",
        "\n".join(lines),
        user_id,
    )

    await set_data(user_id, "reseller_capacity_code", str(account.code))
    await set_data(user_id, "reseller_capacity_quantity", str(quantity))
    await set_data(user_id, "reseller_capacity_source", source)
    await reseller_flow_edit(event, text, buttons=await build_capacity_confirm_buttons(account.code))
    await set_step(user_id, "reseller_capacity_confirm")


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
        txt = await get_bot_text(key="start_message", default=DEFAULT_START_MESSAGE, lang=lang)
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
        await reseller_flow_edit(
            event,
            await get_reseller_text(
                "reseller_select_plan_prompt",
                f"**پنل {panel_name}**\n\nپلن نمایندگی را انتخاب کنید:",
                user_id,
                panel_name=panel_name,
            ),
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
        await _clear_reseller_discount(user_id)
        await set_data(user_id, "reseller_plan_id", str(plan_id))
        if requires_volume_input(plan):
            unit = volume_unit_label(plan.pricing_mode)
            await reseller_flow_edit(
                event,
                f"**{pricing_mode_label(plan.pricing_mode)}**\n\n"
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
        if not plan or plan.pricing_mode != "fixed":
            await event.answer("کد تخفیف فقط برای پلن ثابت است.", alert=True)
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
        await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_pause:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        ok, msg = await pause_reseller_account(acc)
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
        if await _reject_if_admin_locked(event, acc):
            return
        ok, msg = await resume_reseller_account(acc)
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
        if acc.pricing_mode != "usage":
            await event.answer("این گزارش فقط برای پلن مصرفی است.", alert=True)
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
        await delete_data(event.sender_id, "reseller_usage_cap_code")
        await set_step(event.sender_id, "home")
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        used = 0
        if panel:
            try:
                admin = await get_reseller_admin(panel, acc.username)
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
        ok, msg = await set_reseller_usage_cap(acc, gigabytes=None, actor_id=event.sender_id)
        await event.answer(msg, alert=True)
        if ok:
            ok, acc = await ResellerAccountCRUD().get_account(code)
            if ok:
                await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_capacity_amount:"):
        parts = data.split(":")
        code = int(parts[1])
        quantity = int(parts[2])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        if not panel or not panel_reseller_capacity_enabled(panel):
            await event.answer("خرید ظرفیت کاربر برای این پنل فعال نیست.", alert=True)
            return
        await _show_capacity_confirm(event, acc, panel, quantity, source="preset")
        return

    if data.startswith("ResellerAccount_capacity_custom:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        if not panel or not panel_reseller_capacity_enabled(panel):
            await event.answer("خرید ظرفیت کاربر برای این پنل فعال نیست.", alert=True)
            return
        await set_data(user_id, "reseller_capacity_code", str(code))
        await set_step(user_id, "reseller_capacity_custom_input")
        await reseller_flow_edit(
            event,
            await get_reseller_text(
                "reseller_capacity_custom_prompt",
                f"**🔢 تعداد کاربر دلخواه — `{acc.username}`**\n\n"
                f"تعداد کاربر اضافه‌ای که می‌خواهید بخرید را وارد کنید (حداکثر {CAPACITY_CUSTOM_MAX:,}):",
                user_id,
            ),
            buttons=[[await rs_buttons.rs_capacity_back_button(code)]],
        )
        return

    if data.startswith("ResellerAccount_capacity_confirm:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        if await get_step(user_id) != "reseller_capacity_confirm":
            await event.answer("نشست منقضی شده.", alert=True)
            return
        stored_code = await get_data(user_id, "reseller_capacity_code")
        quantity_raw = await get_data(user_id, "reseller_capacity_quantity")
        if not stored_code or int(stored_code) != code or not quantity_raw:
            await event.answer("نشست منقضی شده.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        if not panel or not panel_reseller_capacity_enabled(panel):
            await event.answer("خرید ظرفیت کاربر برای این پنل فعال نیست.", alert=True)
            return

        if not await acquire_user_lock(user_id, "reseller_capacity_buy", ttl=20):
            await event.answer("درخواست قبلی در حال پردازش است.", alert=True)
            return
        source = await get_data(user_id, "reseller_capacity_source") or "preset"
        try:
            success, msg = await increase_reseller_capacity(
                acc,
                panel,
                quantity=int(quantity_raw),
                telegram_id=user_id,
                source=source,
                actor_id=user_id,
            )
        finally:
            await release_user_lock(user_id, "reseller_capacity_buy")

        if not success and msg.startswith("موجودی کافی نیست"):
            await _clear_capacity_state(user_id)
            await set_step(user_id, "home")
            await event.delete()
            await event.respond(msg, buttons=await create_balance_button(user_id))
            return

        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        await event.answer(msg, alert=True)
        ok, acc = await ResellerAccountCRUD().get_account(code)
        if ok:
            await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_capacity_cancel:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        if acc:
            await show_account_detail(event, acc)
        return

    if data.startswith("ResellerAccount_capacity:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        if not panel or not panel_reseller_capacity_enabled(panel):
            await event.answer("خرید ظرفیت کاربر برای این پنل فعال نیست.", alert=True)
            return
        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        await reseller_flow_edit(
            event,
            await get_reseller_text(
                "reseller_capacity_menu",
                f"**👥 خرید ظرفیت کاربر اضافه — `{acc.username}`**\n\n"
                f"👥 User Limit فعلی: {acc.max_users or 0}\n"
                f"💰 قیمت هر کاربر: {panel_reseller_capacity_settings(panel)['price_per_user']:,} تومان\n\n"
                "تعداد کاربر اضافه را انتخاب کنید:",
                user_id,
            ),
            buttons=await build_capacity_preset_buttons(code),
        )
        return

    if data.startswith("ResellerAccount_delete:") and not data.startswith("ResellerAccount_delete_confirm:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        sub_users = 0
        if panel:
            try:
                sub_users = await get_reseller_admin_user_count(panel, acc.username)
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
        if not acc:
            return
        ok, msg = await delete_reseller_account(acc)
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
        if await _reject_if_admin_locked(event, acc):
            return
        await show_account_credentials(event, acc)
        return

    if data.startswith("ResellerAccount_chpwd:"):
        code = int(data.split(":")[1])
        acc = await _get_owned_account(event, code)
        if not acc:
            return
        if await _reject_if_admin_locked(event, acc):
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
        if await _reject_if_admin_locked(event, acc):
            return
        panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return
        try:
            new_password = await reset_reseller_admin_password(panel, acc.username)
        except Exception as exc:
            logger.error("password reset failed: %s", exc)
            await event.answer("خطا در تغییر رمز.", alert=True)
            return
        await ResellerAccountCRUD().update_account(acc.code, password_encrypted=encrypt_data(new_password))
        await send_reseller_log(
            "🔑 تغییر رمز نمایندگی",
            account=acc,
            actor_id=event.sender_id,
        )
        ok, acc = await ResellerAccountCRUD().get_account(code)
        if ok:
            await show_account_credentials(event, acc)
        await event.answer("✅ رمز جدید اعمال شد.", alert=False)
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
        if await _reject_if_admin_locked(event, acc):
            return
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan or not plan.enable or plan.pricing_mode != "fixed":
            await event.answer("پلن نامعتبر است.", alert=True)
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
        if await _reject_if_admin_locked(event, acc):
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
        if await _reject_if_admin_locked(event, acc):
            return
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد.", alert=True)
            return
        amount = calculate_purchase_price(plan)
        discount_code = await get_data(user_id, "reseller_renew_discount_code")
        discounted_raw = await get_data(user_id, "reseller_renew_discount_amount")
        if discount_code and discounted_raw is not None:
            try:
                amount = int(discounted_raw)
            except TypeError, ValueError:
                discount_code = None
        success, msg = await renew_reseller_account(code, plan_id, user_id, amount=amount, discount_code=discount_code)
        await delete_data(user_id, "reseller_renew_discount_code")
        await delete_data(user_id, "reseller_renew_discount_amount")
        await delete_data(user_id, "reseller_renew_plan_id")
        await delete_data(user_id, "reseller_renew_account_code")
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
        if await _reject_if_admin_locked(event, acc):
            return
        if acc.pricing_mode != "fixed":
            await event.answer("تمدید فقط برای پلن‌های ثابت است.", alert=True)
            return
        plans = [
            p
            for p in await ResellerPlanManager().get_all_plans(panel_code=acc.panel_code, enabled_only=True)
            if p.pricing_mode == "fixed"
        ]
        if not plans:
            await event.answer("پلن ثابت فعالی برای این پنل نیست.", alert=True)
            return
        await event.edit(
            f"**💎 تمدید `{acc.username}`**\n\nپلن تمدید را انتخاب کنید:",
            buttons=await build_reseller_renew_plan_buttons(acc.code, plans),
        )
        return


async def _prompt_reseller_username(event, plan):
    user_id = event.sender_id
    await reseller_flow_edit(
        event,
        "**👤 نام کاربری ادمین پنل**\n\nنام کاربری دلخواه را ارسال کنید یا از دکمه زیر استفاده کنید:",
        buttons=[
            [await rs_buttons.rs_buy_random_username_button()],
            [await rs_buttons.rs_buy_back_button("ResellerBuy_back_panels")],
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
    if not plan or plan.pricing_mode != "fixed":
        await event.respond("کد تخفیف فقط برای پلن ثابت است.")
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
    ok, acc = await ResellerAccountCRUD().get_account(int(account_code))
    if not plan or not ok:
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
        and await get_step(event.sender_id) == "reseller_capacity_custom_input"
    )


@bot_is_offline
async def reseller_capacity_custom_message(event: Message):
    user_id = event.sender_id
    code_raw = await get_data(user_id, "reseller_capacity_code")
    if not code_raw:
        await set_step(user_id, "home")
        return
    ok, acc = await ResellerAccountCRUD().get_account(int(code_raw))
    if not ok or acc.telegram_id != user_id:
        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        await event.respond("نمایندگی یافت نشد.")
        return
    if is_admin_locked(acc):
        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        await event.respond("این نمایندگی توسط ادمین غیرفعال شده است.")
        return
    panel = await PanelsManager().get_panel_by_code(code=acc.panel_code)
    if not panel or not panel_reseller_capacity_enabled(panel):
        await _clear_capacity_state(user_id)
        await set_step(user_id, "home")
        await event.respond("خرید ظرفیت کاربر برای این پنل فعال نیست.")
        return

    quantity, error = validate_capacity_quantity(event.message.message)
    if error:
        await event.respond(await get_reseller_text("reseller_capacity_invalid_amount", error, user_id))
        return

    with contextlib.suppress(Exception):
        await event.delete()
    await _show_capacity_confirm(event, acc, panel, quantity, source="custom")


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

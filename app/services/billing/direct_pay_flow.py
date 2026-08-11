"""Shared helpers for direct-pay top-up flow (VPN / reseller / renew)."""

from __future__ import annotations

import asyncio
from typing import Any

from telethon import Button

from app.db.crud.keyboards import get_button_text
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.services.billing import direct_pay_store
from app.telegram.keyboards.balance import create_inline_cartbcard
from app.telegram.state import clear_user, get_data, set_data, set_step
from app.telegram.user.balance.states import (
    BALANCE_FLOW_MSG_STEP,
    CALLBACK_BACK_TO_BALANCE,
    STEP_CART_B_CART,
)
from app.utils.text.bot_texts import get_bot_text

CALLBACK_DIRECT_PAY_TOPUP = "direct_pay_topup"
REDIS_DIRECT_PAY_READY = "direct_pay_ready"
REDIS_DIRECT_PAY_ACTIVE = "direct_pay_active"
REDIS_DIRECT_PAY_AMOUNT = "direct_pay_amount"
REDIS_DIRECT_PAY_KIND = "direct_pay_kind"
REDIS_MABLAGH = "mablagh"

INSUFFICIENT_BALANCE_DEFAULT = (
    "‼️ موجودی کیف پول شما کافی نیست\n\n"
    "💰 برای خرید این پلان شما باید ({required} تومان) موجودی داشته باشید.\n\n"
    "📌 برای افزایش موجودی، روی دکمه 'افزایش موجودی' کلیک کنید و پس از افزایش "
    "با یکی از روش‌های پرداخت، مجدد مراحل خرید را طی کنید."
)

INSUFFICIENT_BALANCE_DIRECT_PAY_DEFAULT = (
    "‼️ موجودی کیف پول شما کافی نیست\n\n"
    "💰 مبلغ لازم برای خرید: ({required} تومان)\n"
    "📉 کمبود موجودی شما: ({shortfall} تومان)\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n\n"
    "📌 روی دکمه «افزایش موجودی» بزنید؛ مبلغ به‌صورت خودکار تنظیم می‌شود و "
    "پس از تایید پرداخت، محصول برای شما ساخته می‌شود."
)

INSUFFICIENT_BALANCE_DIRECT_PAY_RENEW_DEFAULT = (
    "‼️ موجودی کیف پول شما کافی نیست\n\n"
    "💰 مبلغ لازم برای تمدید: ({required} تومان)\n"
    "📉 کمبود موجودی شما: ({shortfall} تومان)\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n\n"
    "📌 روی دکمه «افزایش موجودی» بزنید؛ مبلغ به‌صورت خودکار تنظیم می‌شود و "
    "پس از تایید پرداخت، سرویس شما تمدید می‌شود."
)

DIRECT_PAY_TOPUP_INTRO_DEFAULT = (
    "💳 پرداخت مستقیم خرید\n\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n"
    "💰 مبلغ شارژ: ({topup_amount} تومان)\n"
    "🛒 مبلغ کل خرید: ({required} تومان)\n\n"
    "یک روش پرداخت را انتخاب کنید. نیازی به وارد کردن مبلغ نیست؛ "
    "پس از تایید تراکنش، کانفیگ/پنل برای شما ساخته می‌شود."
)

DIRECT_PAY_RENEW_TOPUP_INTRO_DEFAULT = (
    "💳 پرداخت مستقیم تمدید\n\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n"
    "💰 مبلغ شارژ: ({topup_amount} تومان)\n"
    "🛒 مبلغ کل تمدید: ({required} تومان)\n\n"
    "یک روش پرداخت را انتخاب کنید. نیازی به وارد کردن مبلغ نیست؛ "
    "پس از تایید تراکنش، سرویس شما تمدید می‌شود."
)


def fill_placeholders(template: str, **parts: object) -> str:
    """Replace {key} (and legacy {key:,}) with formatted values."""
    out = template
    for key, raw in parts.items():
        value = f"{raw:,}" if isinstance(raw, int) else str(raw)
        out = out.replace(f"{{{key}:,}}", value).replace(f"{{{key}}}", value)
    return out


def clamp_deposit_amount(amount: int, min_amount: int, max_amount: int) -> int:
    value = max(int(amount), int(min_amount))
    return min(value, int(max_amount))


async def is_direct_pay_enabled() -> bool:
    """Purchase direct-pay toggle (VPN / reseller buy only)."""
    settings = await SettingsManager().get_settings()
    return bool(settings and getattr(settings, "direct_pay_purchase_mode", False))


async def is_direct_pay_renew_enabled() -> bool:
    """Renew direct-pay toggle (VPN config renew only)."""
    settings = await SettingsManager().get_settings()
    return bool(settings and getattr(settings, "direct_pay_renew_mode", False))


async def mark_direct_pay_ready(
    user_id: int,
    *,
    kind: str,
    amount: int,
    product_label: str = "",
    volume: str = "",
) -> None:
    await asyncio.gather(
        set_data(user_id, REDIS_DIRECT_PAY_READY, "1"),
        set_data(user_id, REDIS_DIRECT_PAY_KIND, kind),
        set_data(user_id, REDIS_DIRECT_PAY_AMOUNT, int(amount)),
        set_data(user_id, "direct_pay_product_label", product_label or ""),
        set_data(user_id, "direct_pay_volume", volume or ""),
    )


# Backward-compatible alias used by purchase helpers.
prepare_insufficient_direct_pay = mark_direct_pay_ready


async def build_insufficient_balance_message(
    user_id: int,
    required_amount: int,
    *,
    kind: str,
    product_label: str = "",
    volume: str = "",
    renew: bool = False,
) -> str:
    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    required = int(required_amount)
    shortfall = max(required - balance, 0)
    lang = user.language if user and user.language else "fa"

    use_direct = renew or await is_direct_pay_enabled()
    if use_direct:
        await mark_direct_pay_ready(
            user_id,
            kind=kind,
            amount=required,
            product_label=product_label,
            volume=volume,
        )
        if renew:
            template = await get_bot_text(
                key="insufficient_balance_direct_pay_renew",
                default=INSUFFICIENT_BALANCE_DIRECT_PAY_RENEW_DEFAULT,
                lang=lang,
            )
        else:
            template = await get_bot_text(
                key="insufficient_balance_direct_pay",
                default=INSUFFICIENT_BALANCE_DIRECT_PAY_DEFAULT,
                lang=lang,
            )
        return fill_placeholders(
            template,
            required=required,
            shortfall=shortfall,
            product_label=product_label or "-",
            volume=volume or "-",
            balance=balance,
        )

    template = await get_bot_text(
        key="insufficient_balance_message",
        default=INSUFFICIENT_BALANCE_DEFAULT,
        lang=lang,
    )
    return fill_placeholders(
        template,
        required=required,
        shortfall=shortfall,
        product_label=product_label or "-",
        volume=volume or "-",
        balance=balance,
    )


async def create_balance_button(user_id: int):
    balance_button_text, ready, kind = await asyncio.gather(
        get_button_text("bt.menu_add_balance", "💰 افزایش موجودی"),
        get_data(user_id, REDIS_DIRECT_PAY_READY),
        get_data(user_id, REDIS_DIRECT_PAY_KIND),
    )
    use_direct = False
    if ready and kind:
        if kind == direct_pay_store.KIND_RENEW:
            use_direct = await is_direct_pay_renew_enabled()
        elif kind in {direct_pay_store.KIND_VPN, direct_pay_store.KIND_RESELLER}:
            use_direct = await is_direct_pay_enabled()
    callback = CALLBACK_DIRECT_PAY_TOPUP if use_direct else CALLBACK_BACK_TO_BALANCE
    return [[Button.inline(balance_button_text, data=callback)]]


async def create_direct_pay_balance_button(user_id: int):
    """Always wire the add-balance button to direct-pay top-up callback."""
    balance_button_text = await get_button_text("bt.menu_add_balance", "💰 افزایش موجودی")
    return [[Button.inline(balance_button_text, data=CALLBACK_DIRECT_PAY_TOPUP)]]


async def build_vpn_payload_from_session(user_id: int) -> dict[str, Any]:
    (
        gig,
        panel,
        selected_plan_id,
        username,
        discount_code,
        product_label,
        volume,
        custom_days,
        custom_ip_limit,
        custom_price,
    ) = await asyncio.gather(
        get_data(user_id, "gig"),
        get_data(user_id, "panel"),
        get_data(user_id, "selected_plan_id"),
        get_data(user_id, "username"),
        get_data(user_id, "codetakhfif"),
        get_data(user_id, "direct_pay_product_label"),
        get_data(user_id, "direct_pay_volume"),
        get_data(user_id, "custom_days"),
        get_data(user_id, "custom_ip_limit"),
        get_data(user_id, "custom_price"),
    )
    return {
        "gig": gig,
        "panel": panel,
        "selected_plan_id": selected_plan_id,
        "username": username,
        "discount_code": discount_code,
        "product_label": product_label or "کانفیگ VPN",
        "volume": volume or "",
        "custom_days": custom_days,
        "custom_ip_limit": custom_ip_limit,
        "custom_price": custom_price,
    }


async def build_reseller_payload_from_session(user_id: int) -> dict[str, Any]:
    (
        reseller_plan_id,
        reseller_panel_code,
        reseller_username,
        reseller_volume,
        discount_code,
        product_label,
        volume,
    ) = await asyncio.gather(
        get_data(user_id, "reseller_plan_id"),
        get_data(user_id, "reseller_panel_code"),
        get_data(user_id, "reseller_username"),
        get_data(user_id, "reseller_volume"),
        get_data(user_id, "codetakhfif"),
        get_data(user_id, "direct_pay_product_label"),
        get_data(user_id, "direct_pay_volume"),
    )
    return {
        "reseller_plan_id": reseller_plan_id,
        "reseller_panel_code": reseller_panel_code,
        "reseller_username": reseller_username,
        "reseller_volume": reseller_volume,
        "discount_code": discount_code,
        "product_label": product_label or "پنل نمایندگی",
        "volume": volume or "",
    }


async def build_renew_payload_from_session(user_id: int) -> dict[str, Any]:
    (
        config_name,
        discount,
        discount_code,
        product_label,
        service_code,
        panel,
        selected_plan_id,
        volume,
    ) = await asyncio.gather(
        get_data(user_id, "direct_pay_config_name"),
        get_data(user_id, "codetakhfif"),
        get_data(user_id, "discount_code"),
        get_data(user_id, "direct_pay_product_label"),
        get_data(user_id, "ConfigID"),
        get_data(user_id, "panel"),
        get_data(user_id, "selected_plan_id"),
        get_data(user_id, "direct_pay_volume"),
    )
    config_name = config_name or ""
    if discount is None:
        discount = discount_code
    if not product_label:
        product_label = f"تمدید {config_name}" if config_name else "تمدید"
    return {
        "service_code": service_code,
        "panel": panel,
        "selected_plan_id": selected_plan_id,
        "discount_code": discount,
        "config_name": config_name,
        "product_label": product_label,
        "volume": volume or "",
    }


async def start_direct_pay_topup(event) -> bool:
    """Persist pending purchase/renew to Redis and open payment-method menu with prefilled amount."""
    user_id = event.sender_id
    ready, kind, required_raw = await asyncio.gather(
        get_data(user_id, REDIS_DIRECT_PAY_READY),
        get_data(user_id, REDIS_DIRECT_PAY_KIND),
        get_data(user_id, REDIS_DIRECT_PAY_AMOUNT),
    )
    if not ready or not kind or required_raw is None:
        return False

    if kind == direct_pay_store.KIND_RENEW:
        if not await is_direct_pay_renew_enabled():
            return False
    elif kind in {direct_pay_store.KIND_VPN, direct_pay_store.KIND_RESELLER}:
        if not await is_direct_pay_enabled():
            return False
    else:
        return False

    required = int(required_raw)
    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    shortfall = max(required - balance, 0)
    if shortfall <= 0:
        return False

    if kind == direct_pay_store.KIND_VPN:
        payload = await build_vpn_payload_from_session(user_id)
    elif kind == direct_pay_store.KIND_RESELLER:
        payload = await build_reseller_payload_from_session(user_id)
    else:
        payload = await build_renew_payload_from_session(user_id)

    product_label = str(payload.get("product_label") or "")
    volume = str(payload.get("volume") or "")

    await direct_pay_store.save_pending(
        user_id=user_id,
        kind=str(kind),
        amount=required,
        topup_amount=shortfall,
        payload=payload,
    )

    await clear_user(user_id)
    await asyncio.gather(
        set_data(user_id, REDIS_DIRECT_PAY_ACTIVE, "1"),
        set_data(user_id, REDIS_MABLAGH, shortfall),
        set_data(user_id, REDIS_DIRECT_PAY_AMOUNT, required),
        set_data(user_id, REDIS_DIRECT_PAY_KIND, kind),
        set_data(user_id, "direct_pay_product_label", product_label),
        set_data(user_id, "direct_pay_volume", volume),
    )

    lang = user.language if user and user.language else "fa"
    if kind == direct_pay_store.KIND_RENEW:
        intro_template = await get_bot_text(
            key="direct_pay_renew_topup_intro",
            default=DIRECT_PAY_RENEW_TOPUP_INTRO_DEFAULT,
            lang=lang,
        )
    else:
        intro_template = await get_bot_text(
            key="direct_pay_topup_intro",
            default=DIRECT_PAY_TOPUP_INTRO_DEFAULT,
            lang=lang,
        )
    intro = fill_placeholders(
        intro_template,
        product_label=product_label or "-",
        volume=volume or "-",
        topup_amount=shortfall,
        required=required,
        shortfall=shortfall,
    )
    settings = await SettingsManager().get_settings()
    buttons = await create_inline_cartbcard(settings=settings, user=user)
    try:
        await event.edit(intro, buttons=buttons)
        flow_msg_id = event.message_id
    except Exception:
        sent = await event.respond(intro, buttons=buttons)
        flow_msg_id = sent.id
    await set_data(user_id, BALANCE_FLOW_MSG_STEP, flow_msg_id)
    await set_step(user_id=user_id, step=STEP_CART_B_CART)
    return True


async def is_direct_pay_active(user_id: int) -> bool:
    return bool(await get_data(user_id, REDIS_DIRECT_PAY_ACTIVE))


async def get_direct_pay_prefilled_amount(user_id: int) -> int | None:
    raw = await get_data(user_id, REDIS_MABLAGH)
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None

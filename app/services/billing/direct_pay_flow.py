"""Shared helpers for direct-pay top-up flow (VPN / reseller)."""

from __future__ import annotations

from typing import Any

from telethon import Button

from app.db.crud.keyboards import get_button_text
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.services.billing import direct_pay_store
from app.telegram.keyboards.balance import create_inline_cartbcard
from app.telegram.state import clear_user, get_data, set_data, set_step
from app.telegram.user.balance import states
from app.utils.text.bot_texts import get_bot_text

CALLBACK_DIRECT_PAY_TOPUP = "direct_pay_topup"
REDIS_DIRECT_PAY_READY = "direct_pay_ready"
REDIS_DIRECT_PAY_ACTIVE = "direct_pay_active"
REDIS_DIRECT_PAY_AMOUNT = "direct_pay_amount"
REDIS_DIRECT_PAY_KIND = "direct_pay_kind"
REDIS_MABLAGH = "mablagh"

INSUFFICIENT_BALANCE_DEFAULT = (
    "‼️ موجودی کیف پول شما کافی نیست\n\n"
    "💰 برای خرید این پلان شما باید ({required:,} تومان) موجودی داشته باشید.\n\n"
    "📌 برای افزایش موجودی، روی دکمه 'افزایش موجودی' کلیک کنید و پس از افزایش "
    "با یکی از روش‌های پرداخت، مجدد مراحل خرید را طی کنید."
)

INSUFFICIENT_BALANCE_DIRECT_PAY_DEFAULT = (
    "‼️ موجودی کیف پول شما کافی نیست\n\n"
    "💰 مبلغ لازم برای خرید: ({required:,} تومان)\n"
    "📉 کمبود موجودی شما: ({shortfall:,} تومان)\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n\n"
    "📌 روی دکمه «افزایش موجودی» بزنید؛ مبلغ به‌صورت خودکار تنظیم می‌شود و "
    "پس از تایید پرداخت، محصول برای شما ساخته می‌شود."
)

DIRECT_PAY_TOPUP_INTRO_DEFAULT = (
    "💳 پرداخت مستقیم خرید\n\n"
    "📦 محصول: {product_label}\n"
    "📥 حجم: {volume}\n"
    "💰 مبلغ شارژ: ({topup_amount:,} تومان)\n"
    "🛒 مبلغ کل خرید: ({required:,} تومان)\n\n"
    "یک روش پرداخت را انتخاب کنید. نیازی به وارد کردن مبلغ نیست؛ "
    "پس از تایید تراکنش، کانفیگ/پنل برای شما ساخته می‌شود."
)


def clamp_deposit_amount(amount: int, min_amount: int, max_amount: int) -> int:
    value = max(int(amount), int(min_amount))
    return min(value, int(max_amount))


async def prepare_insufficient_direct_pay(
    user_id: int,
    *,
    kind: str,
    required_amount: int,
    product_label: str = "",
    volume: str = "",
) -> None:
    await set_data(user_id, REDIS_DIRECT_PAY_READY, "1")
    await set_data(user_id, REDIS_DIRECT_PAY_KIND, kind)
    await set_data(user_id, REDIS_DIRECT_PAY_AMOUNT, int(required_amount))
    await set_data(user_id, "direct_pay_product_label", product_label or "")
    await set_data(user_id, "direct_pay_volume", volume or "")


async def build_insufficient_balance_message(
    user_id: int,
    required_amount: int,
    *,
    kind: str,
    product_label: str = "",
    volume: str = "",
) -> str:
    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    required = int(required_amount)
    shortfall = max(required - balance, 0)
    settings = await SettingsManager().get_settings()
    lang = user.language if user and user.language else "fa"

    if settings and getattr(settings, "direct_pay_purchase_mode", False):
        await prepare_insufficient_direct_pay(
            user_id,
            kind=kind,
            required_amount=required,
            product_label=product_label,
            volume=volume,
        )
        template = await get_bot_text(
            key="insufficient_balance_direct_pay",
            default=INSUFFICIENT_BALANCE_DIRECT_PAY_DEFAULT,
            lang=lang,
        )
        return (
            template.replace("{required}", f"{required:,}")
            .replace("{shortfall}", f"{shortfall:,}")
            .replace("{product_label}", product_label or "-")
            .replace("{volume}", volume or "-")
            .replace("{balance}", f"{balance:,}")
        )

    template = await get_bot_text(
        key="insufficient_balance_message",
        default=INSUFFICIENT_BALANCE_DEFAULT,
        lang=lang,
    )
    return (
        template.replace("{required}", f"{required:,}")
        .replace("{shortfall}", f"{shortfall:,}")
        .replace("{product_label}", product_label or "-")
        .replace("{volume}", volume or "-")
        .replace("{balance}", f"{balance:,}")
    )


async def create_balance_button(user_id: int):
    balance_button_text = await get_button_text("bt.menu_add_balance", "💰 افزایش موجودی")
    settings = await SettingsManager().get_settings()
    ready = await get_data(user_id, REDIS_DIRECT_PAY_READY)
    callback = (
        CALLBACK_DIRECT_PAY_TOPUP
        if settings and getattr(settings, "direct_pay_purchase_mode", False) and ready
        else states.CALLBACK_BACK_TO_BALANCE
    )
    return [[Button.inline(balance_button_text, data=callback)]]


async def build_vpn_payload_from_session(user_id: int) -> dict[str, Any]:
    return {
        "gig": await get_data(user_id, "gig"),
        "panel": await get_data(user_id, "panel"),
        "selected_plan_id": await get_data(user_id, "selected_plan_id"),
        "username": await get_data(user_id, "username"),
        "discount_code": await get_data(user_id, "codetakhfif"),
        "product_label": await get_data(user_id, "direct_pay_product_label") or "کانفیگ VPN",
        "volume": await get_data(user_id, "direct_pay_volume") or "",
    }


async def build_reseller_payload_from_session(user_id: int) -> dict[str, Any]:
    return {
        "reseller_plan_id": await get_data(user_id, "reseller_plan_id"),
        "reseller_panel_code": await get_data(user_id, "reseller_panel_code"),
        "reseller_username": await get_data(user_id, "reseller_username"),
        "reseller_volume": await get_data(user_id, "reseller_volume"),
        "discount_code": await get_data(user_id, "codetakhfif"),
        "product_label": await get_data(user_id, "direct_pay_product_label") or "پنل نمایندگی",
        "volume": await get_data(user_id, "direct_pay_volume") or "",
    }


async def start_direct_pay_topup(event) -> bool:
    """Persist pending purchase to Redis and open payment-method menu with prefilled amount."""
    user_id = event.sender_id
    settings = await SettingsManager().get_settings()
    if not settings or not getattr(settings, "direct_pay_purchase_mode", False):
        return False

    ready = await get_data(user_id, REDIS_DIRECT_PAY_READY)
    kind = await get_data(user_id, REDIS_DIRECT_PAY_KIND)
    required_raw = await get_data(user_id, REDIS_DIRECT_PAY_AMOUNT)
    if not ready or not kind or required_raw is None:
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
        return False

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
    await set_data(user_id, REDIS_DIRECT_PAY_ACTIVE, "1")
    await set_data(user_id, REDIS_MABLAGH, shortfall)
    await set_data(user_id, REDIS_DIRECT_PAY_AMOUNT, required)
    await set_data(user_id, REDIS_DIRECT_PAY_KIND, kind)
    await set_data(user_id, "direct_pay_product_label", product_label)
    await set_data(user_id, "direct_pay_volume", volume)

    lang = user.language if user and user.language else "fa"
    intro_template = await get_bot_text(
        key="direct_pay_topup_intro",
        default=DIRECT_PAY_TOPUP_INTRO_DEFAULT,
        lang=lang,
    )
    intro = (
        intro_template.replace("{product_label}", product_label or "-")
        .replace("{volume}", volume or "-")
        .replace("{topup_amount}", f"{shortfall:,}")
        .replace("{required}", f"{required:,}")
        .replace("{shortfall}", f"{shortfall:,}")
    )
    buttons = await create_inline_cartbcard(settings=settings, user=user)
    try:
        await event.edit(intro, buttons=buttons)
    except Exception:
        await event.respond(intro, buttons=buttons)
    await set_step(user_id=user_id, step=states.STEP_CART_B_CART)
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

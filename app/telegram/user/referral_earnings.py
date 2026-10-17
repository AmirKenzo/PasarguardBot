"""Referral earnings: withdraw to card or transfer to the wallet."""

from __future__ import annotations

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.referral import ReferralSettingsCRUD
from app.db.crud.referral_payouts import (
    PAYOUT_CARD,
    PAYOUT_PAID,
    PAYOUT_PENDING,
    PAYOUT_REJECTED,
    PAYOUT_WALLET,
    EarningsSummary,
    ReferralPayoutCRUD,
)
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.telegram.plugins import PluginContext
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import delete_data_many, get_data_many, get_step, set_data_many, set_step
from config import ADMIN_ID

MODULE_NAME = "user.referral_earnings"
MODULE_REQUIRED = True
MODULE_ORDER = 990
MODULE_DESCRIPTION = "Referral earnings: withdrawal and wallet transfer"

logger = get_logger(__name__)

STEP_CARD = "refearn_card"

STEP_HOLDER = "refearn_holder"

KEY_CARD = "refearn_card_number"

KEY_HOLDER = "refearn_card_holder"

CB_HOME = "refearn"

CB_WITHDRAW = "refearn_withdraw"

CB_WITHDRAW_CONFIRM = "refearn_withdraw_confirm"

CB_TRANSFER = "refearn_transfer"

CB_TRANSFER_CONFIRM = "refearn_transfer_confirm"

CB_BACK_TO_INVITE = "referral_invite_friends"

CB_ADMIN_PAID = "refpay_paid:"

CB_ADMIN_REJECT = "refpay_reject:"

CB_ADMIN_VIEW = "refpay_view:"

PAYOUT_STATUS_LABELS = {
    PAYOUT_PENDING: "⏳ در انتظار بررسی",
    PAYOUT_PAID: "✅ پرداخت شد",
    PAYOUT_REJECTED: "❌ رد شد",
}

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_card_number(raw: str) -> str | None:
    """16 digits from a card number typed with Persian digits, spaces or dashes; None if invalid."""
    digits = "".join(ch for ch in (raw or "").translate(_PERSIAN_DIGITS) if ch.isdigit())
    return digits if len(digits) == 16 else None


def format_card(card: str | None) -> str:
    card = card or ""
    return "-".join(card[i : i + 4] for i in range(0, len(card), 4)) if len(card) == 16 else card


def earnings_enabled(settings) -> bool:
    return getattr(settings, "referral_reward_destination", "wallet") == "earnings"


def earnings_text(settings, summary: EarningsSummary) -> str:
    lines = [
        "💼 **درآمد دعوت شما**",
        "",
        f"💰 **قابل برداشت:** `{summary.available:,}` تومان",
    ]
    if summary.requested:
        lines.append(f"⏳ **در حال بررسی:** `{summary.requested:,}` تومان")
    lines += [
        f"✅ **برداشت شده:** `{summary.paid:,}` تومان",
        f"👛 **منتقل‌شده به کیف پول:** `{summary.converted:,}` تومان",
        "",
    ]
    if settings.referral_withdraw_enabled:
        lines.append(f"💳 حداقل مبلغ برداشت به کارت: `{int(settings.referral_withdraw_min or 0):,}` تومان")
    if settings.referral_transfer_enabled:
        lines.append("👛 انتقال به کیف پول فوری انجام می‌شود و می‌توانید با آن خرید کنید.")
    lines.append("")
    lines.append("پاداش هر دعوت بعد از اولین خرید دوستتان به این بخش اضافه می‌شود.")
    return "\n".join(lines)


def earnings_buttons(settings, summary: EarningsSummary) -> list:
    rows = []
    if settings.referral_withdraw_enabled:
        rows.append([Button.inline("💸 برداشت به کارت", data=CB_WITHDRAW)])
    if settings.referral_transfer_enabled:
        rows.append([Button.inline("👛 انتقال به کیف پول", data=CB_TRANSFER)])
    rows.append([Button.inline("🔙 بازگشت", data=CB_BACK_TO_INVITE)])
    return rows


async def load_earnings(user_id: int):
    settings = await ReferralSettingsCRUD().get_settings()
    summary = await ReferralPayoutCRUD().earnings_summary(user_id)
    return settings, summary


def payout_admin_text(payout, *, user_label: str) -> str:
    lines = [
        "💸 **درخواست برداشت درآمد دعوت**",
        "",
        f"🆔 شماره درخواست: `{payout.id}`",
        f"👤 کاربر: {user_label} (`{payout.user_id}`)",
        f"💰 مبلغ: `{payout.amount:,}` تومان",
        f"💳 کارت: `{format_card(payout.card_number)}`",
        f"🧾 صاحب کارت: {payout.card_holder or '—'}",
        f"📌 وضعیت: {PAYOUT_STATUS_LABELS.get(payout.status, payout.status)}",
    ]
    if payout.admin_id and payout.status != PAYOUT_PENDING:
        lines.append(f"👮 بررسی توسط: `{payout.admin_id}`")
    return "\n".join(lines)


def payout_admin_buttons(payout) -> list | None:
    if payout.status != PAYOUT_PENDING:
        return None
    return [
        [
            Button.inline("✅ پرداخت شد", data=f"{CB_ADMIN_PAID}{payout.id}"),
            Button.inline("❌ رد درخواست", data=f"{CB_ADMIN_REJECT}{payout.id}"),
        ]
    ]


async def user_label(user_id: int) -> str:
    try:
        entity = await Kenzo.get_entity(user_id)
        username = getattr(entity, "username", None)
        name = " ".join(filter(None, [getattr(entity, "first_name", None), getattr(entity, "last_name", None)]))
        return f"@{username}" if username else (name or str(user_id))
    except Exception:
        return str(user_id)


async def notify_admins_of_payout(payout) -> None:
    """Every admin gets the request with paid/reject buttons; the first to act settles it."""
    text = payout_admin_text(payout, user_label=await user_label(payout.user_id))
    for admin_id in ADMIN_ID:
        try:
            await Kenzo.send_message(admin_id, text, buttons=payout_admin_buttons(payout))
        except Exception as exc:
            logger.warning("Could not notify admin %s of referral payout %s: %s", admin_id, payout.id, exc)
    await send_log_message(LogType.REFERRAL, message=text)


async def notify_user_of_settlement(payout) -> None:
    if payout.status == PAYOUT_PAID:
        text = (
            "✅ **درخواست برداشت شما پرداخت شد**\n\n"
            f"💰 مبلغ: `{payout.amount:,}` تومان\n"
            f"💳 کارت: `{format_card(payout.card_number)}`\n\n"
            "از اینکه ما را به دوستانتان معرفی می‌کنید ممنونیم 🌹"
        )
    else:
        text = (
            "❌ **درخواست برداشت شما رد شد**\n\n"
            f"💰 مبلغ `{payout.amount:,}` تومان به درآمد قابل برداشت شما برگشت.\n"
            "برای جزئیات با پشتیبانی در ارتباط باشید."
        )
    try:
        await Kenzo.send_message(payout.user_id, text)
    except Exception as exc:
        logger.warning("Could not notify user %s of referral payout %s: %s", payout.user_id, payout.id, exc)


async def current_balance(user_id: int) -> int:
    user = await UserCRUD().read_user(user_id)
    return int(user.amount or 0) if user else 0


__all__ = ["PAYOUT_CARD"]

_USER_CALLBACKS = frozenset(
    {
        CB_HOME,
        CB_WITHDRAW,
        CB_WITHDRAW_CONFIRM,
        CB_TRANSFER,
        CB_TRANSFER_CONFIRM,
    }
)

_BACK = [[Button.inline("🔙 بازگشت به درآمد دعوت", data=CB_HOME)]]

_CANCEL = [[Button.inline("❌ انصراف", data=CB_HOME)]]


async def _show_home(event) -> None:
    settings, summary = await load_earnings(event.sender_id)
    text = earnings_text(settings, summary)
    buttons = earnings_buttons(settings, summary)
    try:
        await event.edit(text, buttons=buttons)
    except Exception:
        await event.respond(text, buttons=buttons)


async def _reset_flow(user_id: int) -> None:
    await delete_data_many(user_id, (KEY_CARD, KEY_HOLDER))
    if await get_step(user_id) in (STEP_CARD, STEP_HOLDER):
        await set_step(user_id, "home")


def _user_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return (event.data or b"").decode("utf-8", "ignore") in _USER_CALLBACKS


@bot_is_offline
@debounce_callback()
async def user_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    user_id = event.sender_id
    settings, summary = await load_earnings(user_id)

    if data == CB_HOME:
        await _reset_flow(user_id)
        await event.answer()
        await _show_home(event)

    elif data == CB_WITHDRAW:
        if not settings.referral_withdraw_enabled:
            await event.answer("برداشت درآمد دعوت فعلاً غیرفعال است.", alert=True)
        elif await ReferralPayoutCRUD().pending_payout(user_id):
            await event.answer("یک درخواست برداشت در حال بررسی دارید.", alert=True)
        elif summary.available < max(int(settings.referral_withdraw_min or 0), 1):
            await event.answer(
                f"حداقل مبلغ برداشت {int(settings.referral_withdraw_min or 0):,} تومان است.\n"
                f"درآمد قابل برداشت شما: {summary.available:,} تومان",
                alert=True,
            )
        else:
            await event.answer()
            await set_step(user_id, STEP_CARD)
            await event.edit(
                "💳 **برداشت به کارت**\n\n"
                f"💰 مبلغ قابل برداشت: `{summary.available:,}` تومان\n\n"
                "شماره کارت ۱۶ رقمی خود را بفرستید:",
                buttons=_CANCEL,
            )

    elif data == CB_WITHDRAW_CONFIRM:
        stored = await get_data_many(user_id, (KEY_CARD, KEY_HOLDER))
        card, holder = stored.get(KEY_CARD), stored.get(KEY_HOLDER)
        if not settings.referral_withdraw_enabled or not card or not holder:
            await event.answer("این درخواست منقضی شده؛ دوباره از ابتدا اقدام کنید.", alert=True)
            await _reset_flow(user_id)
            await _show_home(event)
            return
        payout, error = await ReferralPayoutCRUD().cash_out(
            user_id,
            method=PAYOUT_CARD,
            min_amount=int(settings.referral_withdraw_min or 0),
            card_number=str(card),
            card_holder=str(holder),
        )
        await _reset_flow(user_id)
        if payout is None:
            await event.answer(error, alert=True)
            await _show_home(event)
            return
        await event.answer()
        await event.edit(
            "✅ **درخواست برداشت شما ثبت شد**\n\n"
            f"🆔 شماره درخواست: `{payout.id}`\n"
            f"💰 مبلغ: `{payout.amount:,}` تومان\n"
            f"💳 کارت: `{format_card(payout.card_number)}`\n\n"
            "پس از واریز توسط ادمین، نتیجه برای شما ارسال می‌شود.",
            buttons=_BACK,
        )
        await notify_admins_of_payout(payout)

    elif data == CB_TRANSFER:
        if not settings.referral_transfer_enabled:
            await event.answer("انتقال به کیف پول فعلاً غیرفعال است.", alert=True)
        elif summary.available <= 0:
            await event.answer("درآمد قابل انتقالی ندارید.", alert=True)
        else:
            await event.answer()
            await event.edit(
                "👛 **انتقال درآمد دعوت به کیف پول**\n\n"
                f"💰 مبلغ `{summary.available:,}` تومان به کیف پول شما منتقل می‌شود.\n"
                "⚠️ مبلغ منتقل‌شده دیگر قابل برداشت به کارت نیست و فقط برای خرید استفاده می‌شود.\n\n"
                "تایید می‌کنید؟",
                buttons=[
                    [Button.inline("✅ بله، منتقل کن", data=CB_TRANSFER_CONFIRM)],
                    [Button.inline("❌ انصراف", data=CB_HOME)],
                ],
            )

    elif data == CB_TRANSFER_CONFIRM:
        if not settings.referral_transfer_enabled:
            await event.answer("انتقال به کیف پول فعلاً غیرفعال است.", alert=True)
            return
        payout, error = await ReferralPayoutCRUD().cash_out(user_id, method=PAYOUT_WALLET)
        if payout is None:
            await event.answer(error, alert=True)
            await _show_home(event)
            return
        await event.answer()
        await event.edit(
            "✅ **انتقال انجام شد**\n\n"
            f"💰 مبلغ `{payout.amount:,}` تومان به کیف پول شما اضافه شد.\n"
            f"👛 موجودی فعلی کیف پول: `{await current_balance(user_id):,}` تومان",
            buttons=_BACK,
        )
    raise events.StopPropagation


async def _step_filter(event: Message) -> bool:
    if not event.is_private:
        return False
    return await get_step(event.sender_id) in (STEP_CARD, STEP_HOLDER)


@bot_is_offline
async def step_message(event: Message):
    user_id = event.sender_id
    text = (event.message.message or "").strip()
    step = await get_step(user_id)

    if step == STEP_CARD:
        card = normalize_card_number(text)
        if card is None:
            await event.respond("❌ شماره کارت باید ۱۶ رقم باشد. دوباره بفرستید:", buttons=_CANCEL)
            raise events.StopPropagation
        await set_data_many(user_id, {KEY_CARD: card})
        await set_step(user_id, STEP_HOLDER)
        await event.respond("🧾 نام و نام خانوادگی صاحب کارت را بفرستید:", buttons=_CANCEL)
        raise events.StopPropagation

    holder = " ".join(text.split())
    if not 3 <= len(holder) <= 60:
        await event.respond("❌ نام صاحب کارت باید بین ۳ تا ۶۰ حرف باشد. دوباره بفرستید:", buttons=_CANCEL)
        raise events.StopPropagation
    stored = await get_data_many(user_id, (KEY_CARD,))
    card = stored.get(KEY_CARD)
    if not card:
        await _reset_flow(user_id)
        await event.respond("این درخواست منقضی شده؛ دوباره از ابتدا اقدام کنید.", buttons=_BACK)
        raise events.StopPropagation
    await set_data_many(user_id, {KEY_HOLDER: holder})
    await set_step(user_id, "home")
    _settings, summary = await load_earnings(user_id)
    await event.respond(
        "📋 **تایید درخواست برداشت**\n\n"
        f"💰 مبلغ: `{summary.available:,}` تومان\n"
        f"💳 کارت: `{format_card(str(card))}`\n"
        f"🧾 صاحب کارت: {holder}\n\n"
        "اطلاعات درست است؟",
        buttons=[
            [Button.inline("✅ تایید و ارسال درخواست", data=CB_WITHDRAW_CONFIRM)],
            [Button.inline("❌ انصراف", data=CB_HOME)],
        ],
    )
    raise events.StopPropagation


def _admin_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = (event.data or b"").decode("utf-8", "ignore")
    return data.startswith((CB_ADMIN_PAID, CB_ADMIN_REJECT, CB_ADMIN_VIEW))


async def admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    paid = data.startswith(CB_ADMIN_PAID)
    raw_id = data.split(":", 1)[1]
    if not raw_id.isdigit():
        await event.answer("شناسه نامعتبر است.", alert=True)
        raise events.StopPropagation

    if data.startswith(CB_ADMIN_VIEW):
        payout = await ReferralPayoutCRUD().get_payout(int(raw_id))
        if payout is None:
            await event.answer("درخواست پیدا نشد.", alert=True)
            raise events.StopPropagation
        await event.answer()
        buttons = payout_admin_buttons(payout) or []
        buttons.append([Button.inline("🔙 بازگشت به لیست", data="referral_pending_payouts")])
        text = payout_admin_text(payout, user_label=await user_label(payout.user_id))
        await event.edit(text, buttons=buttons)
        raise events.StopPropagation

    payout, error = await ReferralPayoutCRUD().settle(int(raw_id), admin_id=event.sender_id, paid=paid)
    if payout is None:
        await event.answer(error, alert=True)
        raise events.StopPropagation
    text = payout_admin_text(payout, user_label=await user_label(payout.user_id))
    with contextlib.suppress(Exception):
        await event.edit(text, buttons=payout_admin_buttons(payout))
    if error:
        # Another admin settled it first; this copy just catches up.
        await event.answer(error, alert=True)
        raise events.StopPropagation
    await event.answer("✅ ثبت شد." if paid else "❌ رد شد و مبلغ به درآمد کاربر برگشت.")
    await notify_user_of_settlement(payout)
    raise events.StopPropagation


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(user_callback, events.CallbackQuery(func=_user_callback_filter))
    ctx.add_event_handler(admin_callback, events.CallbackQuery(func=_admin_callback_filter))
    ctx.add_event_handler(step_message, events.NewMessage(incoming=True, func=_step_filter))

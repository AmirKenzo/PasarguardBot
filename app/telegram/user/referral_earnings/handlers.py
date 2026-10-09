"""Handlers for referral earnings: user screens and steps, admin paid/reject."""

from __future__ import annotations

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.referral_payouts import PAYOUT_CARD, PAYOUT_WALLET, ReferralPayoutCRUD
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import delete_data_many, get_data_many, get_step, set_data_many, set_step
from app.telegram.user.referral_earnings import service
from config import ADMIN_ID

_USER_CALLBACKS = frozenset(
    {
        service.CB_HOME,
        service.CB_WITHDRAW,
        service.CB_WITHDRAW_CONFIRM,
        service.CB_TRANSFER,
        service.CB_TRANSFER_CONFIRM,
    }
)
_BACK = [[Button.inline("🔙 بازگشت به درآمد دعوت", data=service.CB_HOME)]]
_CANCEL = [[Button.inline("❌ انصراف", data=service.CB_HOME)]]


async def _show_home(event) -> None:
    settings, summary = await service.load_earnings(event.sender_id)
    text = service.earnings_text(settings, summary)
    buttons = service.earnings_buttons(settings, summary)
    try:
        await event.edit(text, buttons=buttons)
    except Exception:
        await event.respond(text, buttons=buttons)


async def _reset_flow(user_id: int) -> None:
    await delete_data_many(user_id, (service.KEY_CARD, service.KEY_HOLDER))
    if await get_step(user_id) in (service.STEP_CARD, service.STEP_HOLDER):
        await set_step(user_id, "home")


def _user_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return (event.data or b"").decode("utf-8", "ignore") in _USER_CALLBACKS


@bot_is_offline
@debounce_callback()
async def user_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    user_id = event.sender_id
    settings, summary = await service.load_earnings(user_id)

    if data == service.CB_HOME:
        await _reset_flow(user_id)
        await event.answer()
        await _show_home(event)

    elif data == service.CB_WITHDRAW:
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
            await set_step(user_id, service.STEP_CARD)
            await event.edit(
                "💳 **برداشت به کارت**\n\n"
                f"💰 مبلغ قابل برداشت: `{summary.available:,}` تومان\n\n"
                "شماره کارت ۱۶ رقمی خود را بفرستید:",
                buttons=_CANCEL,
            )

    elif data == service.CB_WITHDRAW_CONFIRM:
        stored = await get_data_many(user_id, (service.KEY_CARD, service.KEY_HOLDER))
        card, holder = stored.get(service.KEY_CARD), stored.get(service.KEY_HOLDER)
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
            f"💳 کارت: `{service.format_card(payout.card_number)}`\n\n"
            "پس از واریز توسط ادمین، نتیجه برای شما ارسال می‌شود.",
            buttons=_BACK,
        )
        await service.notify_admins_of_payout(payout)

    elif data == service.CB_TRANSFER:
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
                    [Button.inline("✅ بله، منتقل کن", data=service.CB_TRANSFER_CONFIRM)],
                    [Button.inline("❌ انصراف", data=service.CB_HOME)],
                ],
            )

    elif data == service.CB_TRANSFER_CONFIRM:
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
            f"👛 موجودی فعلی کیف پول: `{await service.current_balance(user_id):,}` تومان",
            buttons=_BACK,
        )
    raise events.StopPropagation


async def _step_filter(event: Message) -> bool:
    if not event.is_private:
        return False
    return await get_step(event.sender_id) in (service.STEP_CARD, service.STEP_HOLDER)


@bot_is_offline
async def step_message(event: Message):
    user_id = event.sender_id
    text = (event.message.message or "").strip()
    step = await get_step(user_id)

    if step == service.STEP_CARD:
        card = service.normalize_card_number(text)
        if card is None:
            await event.respond("❌ شماره کارت باید ۱۶ رقم باشد. دوباره بفرستید:", buttons=_CANCEL)
            raise events.StopPropagation
        await set_data_many(user_id, {service.KEY_CARD: card})
        await set_step(user_id, service.STEP_HOLDER)
        await event.respond("🧾 نام و نام خانوادگی صاحب کارت را بفرستید:", buttons=_CANCEL)
        raise events.StopPropagation

    holder = " ".join(text.split())
    if not 3 <= len(holder) <= 60:
        await event.respond("❌ نام صاحب کارت باید بین ۳ تا ۶۰ حرف باشد. دوباره بفرستید:", buttons=_CANCEL)
        raise events.StopPropagation
    stored = await get_data_many(user_id, (service.KEY_CARD,))
    card = stored.get(service.KEY_CARD)
    if not card:
        await _reset_flow(user_id)
        await event.respond("این درخواست منقضی شده؛ دوباره از ابتدا اقدام کنید.", buttons=_BACK)
        raise events.StopPropagation
    await set_data_many(user_id, {service.KEY_HOLDER: holder})
    await set_step(user_id, "home")
    _settings, summary = await service.load_earnings(user_id)
    await event.respond(
        "📋 **تایید درخواست برداشت**\n\n"
        f"💰 مبلغ: `{summary.available:,}` تومان\n"
        f"💳 کارت: `{service.format_card(str(card))}`\n"
        f"🧾 صاحب کارت: {holder}\n\n"
        "اطلاعات درست است؟",
        buttons=[
            [Button.inline("✅ تایید و ارسال درخواست", data=service.CB_WITHDRAW_CONFIRM)],
            [Button.inline("❌ انصراف", data=service.CB_HOME)],
        ],
    )
    raise events.StopPropagation


def _admin_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = (event.data or b"").decode("utf-8", "ignore")
    return data.startswith((service.CB_ADMIN_PAID, service.CB_ADMIN_REJECT, service.CB_ADMIN_VIEW))


async def admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    paid = data.startswith(service.CB_ADMIN_PAID)
    raw_id = data.split(":", 1)[1]
    if not raw_id.isdigit():
        await event.answer("شناسه نامعتبر است.", alert=True)
        raise events.StopPropagation

    if data.startswith(service.CB_ADMIN_VIEW):
        payout = await ReferralPayoutCRUD().get_payout(int(raw_id))
        if payout is None:
            await event.answer("درخواست پیدا نشد.", alert=True)
            raise events.StopPropagation
        await event.answer()
        buttons = service.payout_admin_buttons(payout) or []
        buttons.append([Button.inline("🔙 بازگشت به لیست", data="referral_pending_payouts")])
        text = service.payout_admin_text(payout, user_label=await service.user_label(payout.user_id))
        await event.edit(text, buttons=buttons)
        raise events.StopPropagation

    payout, error = await ReferralPayoutCRUD().settle(int(raw_id), admin_id=event.sender_id, paid=paid)
    if payout is None:
        await event.answer(error, alert=True)
        raise events.StopPropagation
    text = service.payout_admin_text(payout, user_label=await service.user_label(payout.user_id))
    with contextlib.suppress(Exception):
        await event.edit(text, buttons=service.payout_admin_buttons(payout))
    if error:
        # Another admin settled it first; this copy just catches up.
        await event.answer(error, alert=True)
        raise events.StopPropagation
    await event.answer("✅ ثبت شد." if paid else "❌ رد شد و مبلغ به درآمد کاربر برگشت.")
    await service.notify_user_of_settlement(payout)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(user_callback, events.CallbackQuery(func=_user_callback_filter))
    client.add_event_handler(admin_callback, events.CallbackQuery(func=_admin_callback_filter))
    client.add_event_handler(step_message, events.NewMessage(incoming=True, func=_step_filter))

"""Referral earnings screens: balance, card withdrawal, wallet transfer, admin review.

Every amount shown or moved here is read from the reward ledger at that moment
(crud/referral_payouts.py); nothing the user typed or a button carried decides
how much is paid. Buttons only carry fixed tokens and a payout id.
"""

from __future__ import annotations

from telethon import Button

from app import Kenzo
from app.db.crud.referral import ReferralSettingsCRUD
from app.db.crud.referral_payouts import (
    PAYOUT_CARD,
    PAYOUT_PAID,
    PAYOUT_PENDING,
    PAYOUT_REJECTED,
    EarningsSummary,
    ReferralPayoutCRUD,
)
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.telegram.shared.utils.logging import send_log_message
from config import ADMIN_ID

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

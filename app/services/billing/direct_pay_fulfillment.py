"""Fulfill direct-pay purchases/renewals after wallet credit (Redis pending, no DB table)."""

from __future__ import annotations

from typing import Any

from app import Kenzo
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing import direct_pay_store
from app.services.billing.direct_pay_renew import create_vpn_renew_for_user
from app.telegram.user.reseller.helpers import create_reseller_purchase_for_user
from app.telegram.user.shop.helpers import create_vpn_purchase_for_user
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)

FULFILL_FAILED_DEFAULT = (
    "موجودی شما شارژ شد، اما ساخت خودکار محصول انجام نشد.\n"
    "لطفاً دوباره از منوی خرید اقدام کنید یا با پشتیبانی تماس بگیرید.\n"
    "💰 موجودی فعلی: `{balance}` تومان"
)

RENEW_FULFILL_FAILED_DEFAULT = (
    "موجودی شما شارژ شد، اما تمدید خودکار سرویس انجام نشد.\n"
    "لطفاً دوباره از منوی سرویس‌ها تمدید را انجام دهید یا با پشتیبانی تماس بگیرید.\n"
    "💰 موجودی فعلی: `{balance}` تومان"
)

DIRECT_PAY_CANCELLED_DEFAULT = "سفارش پرداخت مستقیم شما لغو شد.\nدر صورت نیاز دوباره مراحل خرید را طی کنید."


async def _notify_fulfill_failed(user_id: int, balance: int, *, renew: bool = False) -> None:
    if renew:
        text = await get_bot_text(
            key="direct_pay_renew_fulfill_failed",
            default=RENEW_FULFILL_FAILED_DEFAULT,
            lang="fa",
        )
    else:
        text = await get_bot_text(
            key="direct_pay_fulfill_failed",
            default=FULFILL_FAILED_DEFAULT,
            lang="fa",
        )
    message = text.replace("{balance}", f"{int(balance):,}")
    try:
        await Kenzo.send_message(int(user_id), message)
    except Exception as exc:
        logger.warning("direct_pay fulfill_failed notify user=%s: %s", user_id, exc)


async def notify_direct_pay_cancelled(user_id: int) -> None:
    text = await get_bot_text(
        key="direct_pay_cancelled",
        default=DIRECT_PAY_CANCELLED_DEFAULT,
        lang="fa",
    )
    try:
        await Kenzo.send_message(int(user_id), text)
    except Exception as exc:
        logger.warning("direct_pay cancelled notify user=%s: %s", user_id, exc)


async def fulfill_pending_record(record: dict[str, Any]) -> bool:
    """Create product or renew for a claimed pending record. Returns True on success."""
    user_id = int(record["user_id"])
    kind = record.get("kind")
    amount = int(record.get("amount") or 0)
    payload = record.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    is_renew = kind == direct_pay_store.KIND_RENEW

    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else 0
    if balance < amount:
        await direct_pay_store.mark_status(user_id, "failed")
        await _notify_fulfill_failed(user_id, balance, renew=is_renew)
        return False

    try:
        if kind == direct_pay_store.KIND_VPN:
            ok, err = await create_vpn_purchase_for_user(
                user_id,
                amount=amount,
                payload=payload,
                discount_code=payload.get("discount_code"),
            )
        elif kind == direct_pay_store.KIND_RESELLER:
            ok, err = await create_reseller_purchase_for_user(
                user_id,
                amount=amount,
                payload=payload,
                discount_code=payload.get("discount_code"),
            )
        elif is_renew:
            ok, err = await create_vpn_renew_for_user(
                user_id,
                amount=amount,
                payload=payload,
                discount_code=payload.get("discount_code"),
            )
        else:
            ok, err = False, "unknown_kind"
    except Exception as exc:
        logger.exception("direct_pay fulfill error user=%s: %s", user_id, exc)
        ok, err = False, str(exc)

    if ok:
        await direct_pay_store.mark_status(user_id, "fulfilled")
        await direct_pay_store.clear_pending(user_id)
        return True

    logger.warning("direct_pay fulfill failed user=%s kind=%s err=%s", user_id, kind, err)
    await direct_pay_store.mark_status(user_id, "failed")
    user = await UserCRUD().read_user(user_id)
    balance = int(user.amount or 0) if user else balance
    await _notify_fulfill_failed(user_id, balance, renew=is_renew)
    return False


async def try_fulfill_after_manual_credit(transaction_id: int) -> bool:
    record = await direct_pay_store.get_pending_by_transaction_id(int(transaction_id))
    if not record:
        return False
    claimed = await direct_pay_store.claim_for_fulfillment(int(record["user_id"]))
    if not claimed:
        return False
    return await fulfill_pending_record(claimed)


async def try_fulfill_after_crypto_credit(crypto_order_id: int) -> bool:
    record = await direct_pay_store.get_pending_by_crypto_order_id(int(crypto_order_id))
    if not record:
        return False
    claimed = await direct_pay_store.claim_for_fulfillment(int(record["user_id"]))
    if not claimed:
        return False
    return await fulfill_pending_record(claimed)


async def cancel_after_manual_reject(transaction_id: int) -> None:
    record = await direct_pay_store.cancel_by_transaction_id(int(transaction_id))
    if record:
        await notify_direct_pay_cancelled(int(record["user_id"]))


async def cancel_after_crypto_expire(crypto_order_id: int) -> None:
    record = await direct_pay_store.cancel_by_crypto_order_id(int(crypto_order_id))
    if record:
        await notify_direct_pay_cancelled(int(record["user_id"]))

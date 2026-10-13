"""ForApp matching service: match a bank-deposit SMS to a pending manual top-up.

Separated from the FastAPI router so it can be unit-tested without HTTP.
"""

from __future__ import annotations

import contextlib
import time
import uuid

from telethon import Button

from app import Kenzo
from app.db.crud.bank_deposits import BankDepositCRUD
from app.db.crud.transactions import TransactionCRUD
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import try_fulfill_after_manual_credit
from app.services.payments.forapp import coerce_raw_amount, forapp_candidates, normalize_to_toman
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

FORAPP_APPROVED_USER_MESSAGE = (
    "✅ پرداخت کارت‌به‌کارت شما به صورت خودکار تایید شد.\n\n"
    "💵 مبلغ واریزی: `{payable}` تومان\n"
    "💳 موجودی جدید: `{balance}` تومان{bonus_line}"
)


def _str(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return None


def _payload_data(payload: dict) -> dict:
    """ForApp may wrap the SMS in a ``data`` envelope — unwrap one level."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return {**payload, **payload["data"]}
    return payload


def extract_deposit_fields(payload: dict, *, fallback_id: str | None = None) -> dict:
    """Leniently extract normalized deposit fields from a ForApp POST body.

    Field names mirror the app's default JSON template (see ForApp
    ``Request.defaultBody``): ``id``, ``test``, ``sender``, ``bank``,
    ``body``, ``amount``, ``code`` (last 3 digits of amount), ``unit``,
    ``is_deposit`` (nullable), ``received_at``/``received_at_ms``,
    ``attempt``, ``device``. ``fallback_id`` is the ``Idempotency-Key``
    header, used only when the body carries no id.
    """
    data = _payload_data(payload if isinstance(payload, dict) else {})

    deposit_id = _str(data, "id", "message_id", "sms_id", "deposit_id", "uuid")
    if not deposit_id and fallback_id and fallback_id.strip():
        deposit_id = fallback_id.strip()
    if not deposit_id:
        # Stable fallback so retries with identical content still dedupe.
        seed = "|".join(
            [
                str(_str(data, "sender", "from", "address") or ""),
                str(_str(data, "body", "text", "message", "sms") or ""),
                str(data.get("raw_amount") or data.get("amount") or ""),
                str(data.get("received_at_ms") or data.get("received_at") or ""),
            ]
        )
        deposit_id = f"forapp_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"

    raw = coerce_raw_amount(
        data.get("raw_amount", data.get("amount", data.get("value", data.get("price"))))
    )
    unit = _str(data, "unit", "currency")  # None = unknown; normalized as rial
    sender = _str(data, "sender", "from", "address", "bank_sender")
    bank = _str(data, "bank", "bank_name")
    body = _str(data, "body", "text", "message", "sms") or ""
    code = _str(data, "code", "ref", "ref_id", "tracking", "followup", "follow_up", "transaction_id")
    device = _str(data, "device", "device_name")
    received_at_ms = data.get("received_at_ms", data.get("received_at", data.get("timestamp")))
    try:
        received_at_ms = int(received_at_ms) if received_at_ms else None
    except (TypeError, ValueError):
        received_at_ms = None
    try:
        attempt = int(data.get("attempt", 1) or 1)
    except (TypeError, ValueError):
        attempt = 1
    is_test = bool(data.get("is_test", data.get("test", False)))
    if not is_test and deposit_id.startswith("test-"):
        # The app's own "send test" button uses ids like "test-<uuid>".
        is_test = True

    is_deposit: bool | None = data.get("is_deposit", data.get("isDeposit"))
    # The app sends null when it cannot tell; treat as a deposit candidate and
    # let amount matching decide (unmatched ones stay for admin review).
    if is_deposit is None:
        kind = str(data.get("type", data.get("kind", ""))).lower()
        is_deposit = kind not in ("withdraw", "withdrawal", "برداشت", "purchase", "buy", "خرید")
    else:
        is_deposit = bool(is_deposit)

    amount_toman = normalize_to_toman(raw, unit) if raw else None
    return {
        "deposit_id": deposit_id,
        "raw": raw,
        "unit": unit,
        "sender": sender,
        "bank": bank,
        "body": body,
        "code": code,
        "device": device,
        "received_at_ms": received_at_ms,
        "attempt": attempt,
        "is_test": is_test,
        "is_deposit": is_deposit,
        "amount_toman": amount_toman,
    }


async def _settings_snapshot():
    from app.db.crud.settings import SettingsManager

    try:
        return await SettingsManager().get_settings()
    except Exception:
        return None


async def process_forapp_deposit(payload: dict, *, fallback_id: str | None = None) -> dict:
    """Store the SMS idempotently, match a pending manual tx, auto-approve it.

    Returns a dict with ``status`` in
    ``matched | unmatched | ignored | test | invalid`` plus ids for logging.
    """
    fields = extract_deposit_fields(payload, fallback_id=fallback_id)
    crud = BankDepositCRUD()
    deposit = await crud.upsert(
        deposit_id=fields["deposit_id"],
        raw_amount=fields["raw"],
        amount_toman=fields["amount_toman"],
        unit=fields["unit"],
        sender=fields["sender"],
        bank=fields["bank"],
        body=((fields["body"] or "") + (f"\nref:{fields['code']}" if fields["code"] else ""))[:4000] or None,
        is_deposit=fields["is_deposit"],
        received_at_ms=fields["received_at_ms"],
        device=fields["device"],
        attempt=fields["attempt"],
        is_test=fields["is_test"],
    )
    if deposit is None:
        return {"status": "invalid", "deposit_id": fields["deposit_id"]}

    # Already matched on a previous delivery — idempotent replay.
    if deposit.status == "matched":
        return {"status": "matched", "deposit_id": deposit.id, "tx_id": deposit.matched_tx_id}

    if fields["is_test"]:
        await crud.mark_status(deposit.id, "test")
        return {"status": "test", "deposit_id": deposit.id}

    if not fields["is_deposit"]:
        await crud.mark_status(deposit.id, "ignored")
        return {"status": "ignored", "deposit_id": deposit.id}

    if not fields["raw"]:
        await crud.mark_status(deposit.id, "unmatched")
        return {"status": "unmatched", "deposit_id": deposit.id}

    settings = await _settings_snapshot()
    ttl_minutes = int(getattr(settings, "forapp_ttl_minutes", 30) or 30) if settings else 30
    since = int(time.time()) - ttl_minutes * 60 if ttl_minutes > 0 else None

    candidates = forapp_candidates(fields["raw"], fields["unit"])
    tx_crud = TransactionCRUD()
    matched = None
    for candidate in candidates:
        matched = await tx_crud.find_pending_manual_by_payable(candidate, since_ts=since)
        if matched:
            break

    if matched is None:
        await crud.mark_status(deposit.id, "unmatched")
        try:
            await send_log_message(
                LogType.MANUAL_CARD,
                message=(
                    "🏦 #واریز_بانکی_بدون_تطبیق\n"
                    f"💰 مبلغ: `{fields['amount_toman']:,}` تومان\n"
                    f"🏦 بانک: {fields['bank'] or '-'}\n"
                    f"📨 فرستنده: `{fields['sender'] or '-'}`\n"
                    f"🔖 شناسه پیامک: `{deposit.id}`"
                    + (f"\n🧾 پیگیری: `{fields['code']}`" if fields["code"] else "")
                ),
            )
        except Exception as exc:
            logger.warning("forapp unmatched log failed: %s", exc)
        return {"status": "unmatched", "deposit_id": deposit.id}

    result = await tx_crud.approve_manual(matched)
    if not result:
        await crud.mark_status(deposit.id, "unmatched")
        return {"status": "unmatched", "deposit_id": deposit.id}

    await crud.mark_matched(deposit.id, tx_id=int(matched.id), user_id=int(matched.user_id))
    new_balance = int(result["new_balance"])
    bonus = int(result["bonus"])
    bonus_line = f"\n🎁 بونوس: +{bonus:,} تومان" if bonus > 0 else ""
    payable = int(matched.payable_amount or matched.amount)

    try:
        fulfilled = await try_fulfill_after_manual_credit(int(matched.id))
        if not fulfilled:
            await Kenzo.send_message(
                int(matched.user_id),
                "⚡ پرداخت کارت‌به‌کارت شما به صورت خودکار تایید شد.\n\n"
                f"💵 مبلغ واریزی: `{payable:,}` تومان\n"
                f"💳 موجودی جدید: `{new_balance:,}` تومان{bonus_line}",
                buttons=[[Button.inline(text=f"موجودی جدید {new_balance:,} تومان", data="no_action")]],
            )
    except Exception as exc:
        logger.warning("forapp user notify failed tx=%s: %s", matched.id, exc)

    try:
        await send_log_message(
            LogType.MANUAL_CARD,
            message=(
                "⚡ #کارت_به‌کارت_خودکار\n"
                f"👤 کاربر: `{matched.user_id}` | [پروفایل](tg://user?id={matched.user_id})\n"
                f"💵 مبلغ واریزی: `{payable:,}` تومان\n"
                f"💳 موجودی جدید: `{new_balance:,}` تومان{bonus_line}\n"
                f"🏦 بانک: {fields['bank'] or '-'}\n"
                f"🔖 پیامک: `{deposit.id}`"
                + (f"\n🧾 پیگیری: `{fields['code']}`" if fields["code"] else "")
            ),
        )
    except Exception as exc:
        logger.warning("forapp match log failed tx=%s: %s", matched.id, exc)

    # Keep the admin receipt message (if the user also sent a photo) consistent.
    if matched.message_id and matched.message_chat_id:
        with contextlib.suppress(Exception):
            await Kenzo.edit_message(
                int(matched.message_chat_id),
                int(matched.message_id),
                f"⚡ تراکنش خودکار تایید شد.\n💵 مبلغ: `{payable:,}` تومان\n💳 موجودی جدید: `{new_balance:,}` تومان",
                buttons=[[Button.inline(text="⚡ تایید خودکار ForApp", data="no_action")]],
            )

    logger.info("forapp matched deposit=%s tx=%s payable=%s", deposit.id, matched.id, payable)
    return {"status": "matched", "deposit_id": deposit.id, "tx_id": int(matched.id)}

"""Redis-backed pending direct-pay purchases (no DB table).

Keys live outside the per-user conversation hash so clear_user does not wipe them.
"""

from __future__ import annotations

import json
import time
from contextlib import suppress
from typing import Any

from app.db.redis import get_redis
from app.logger import get_logger
from app.telegram.state.keys import (
    build_direct_pay_claim_key,
    build_direct_pay_crypto_key,
    build_direct_pay_tx_key,
    build_direct_pay_user_key,
)
from config import LOCK_TTL_SECONDS, STATE_TTL_SECONDS

logger = get_logger(__name__)

ACTIVE_STATUSES = frozenset({"pending", "linked"})
KIND_VPN = "vpn"
KIND_RESELLER = "reseller"
KIND_RENEW = "renew"

DIRECT_PAY_TTL_SECONDS = max(int(STATE_TTL_SECONDS or 86400), 86400)


def _claim_ttl_seconds() -> int:
    return max(int(LOCK_TTL_SECONDS or 300), 60)


def _now() -> int:
    return int(time.time())


async def _set_json(key: str, data: dict[str, Any], ttl: int = DIRECT_PAY_TTL_SECONDS) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(data, ensure_ascii=False), ex=ttl)
    except Exception as exc:
        logger.warning("direct_pay set_json(%s): %s", key, exc)


async def _get_json(key: str) -> dict[str, Any] | None:
    redis = await get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("direct_pay get_json(%s): %s", key, exc)
        return None


async def _delete_key(key: str) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        await redis.delete(key)
    except Exception as exc:
        logger.warning("direct_pay delete(%s): %s", key, exc)


async def _clear_claim(user_id: int) -> None:
    await _delete_key(build_direct_pay_claim_key(user_id))


async def save_pending(
    *,
    user_id: int,
    kind: str,
    amount: int,
    topup_amount: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Replace any active pending for this user and store a new one."""
    existing = await get_pending_for_user(user_id)
    if existing:
        await cancel_pending_for_user(user_id)

    record = {
        "user_id": int(user_id),
        "kind": kind,
        "amount": int(amount),
        "topup_amount": int(topup_amount),
        "payload": payload,
        "status": "pending",
        "transaction_id": None,
        "crypto_order_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await _set_json(build_direct_pay_user_key(user_id), record)
    return record


async def get_pending_for_user(user_id: int) -> dict[str, Any] | None:
    return await _get_json(build_direct_pay_user_key(user_id))


async def _write_user_record(record: dict[str, Any]) -> None:
    user_id = int(record["user_id"])
    record["updated_at"] = _now()
    await _set_json(build_direct_pay_user_key(user_id), record)


async def link_transaction(user_id: int, transaction_id: int) -> dict[str, Any] | None:
    record = await get_pending_for_user(user_id)
    if not record or record.get("status") not in ACTIVE_STATUSES:
        return None
    record["transaction_id"] = int(transaction_id)
    record["status"] = "linked"
    await _write_user_record(record)
    await _set_json(
        build_direct_pay_tx_key(transaction_id),
        {"user_id": int(user_id)},
        ttl=DIRECT_PAY_TTL_SECONDS,
    )
    return record


async def link_crypto_order(user_id: int, crypto_order_id: int) -> dict[str, Any] | None:
    record = await get_pending_for_user(user_id)
    if not record or record.get("status") not in ACTIVE_STATUSES:
        return None
    record["crypto_order_id"] = int(crypto_order_id)
    record["status"] = "linked"
    await _write_user_record(record)
    await _set_json(
        build_direct_pay_crypto_key(crypto_order_id),
        {"user_id": int(user_id)},
        ttl=DIRECT_PAY_TTL_SECONDS,
    )
    return record


async def get_pending_by_transaction_id(transaction_id: int) -> dict[str, Any] | None:
    link = await _get_json(build_direct_pay_tx_key(transaction_id))
    if not link:
        return None
    record = await get_pending_for_user(int(link["user_id"]))
    if not record:
        return None
    if int(record.get("transaction_id") or 0) != int(transaction_id):
        return None
    return record


async def get_pending_by_crypto_order_id(crypto_order_id: int) -> dict[str, Any] | None:
    link = await _get_json(build_direct_pay_crypto_key(crypto_order_id))
    if not link:
        return None
    record = await get_pending_for_user(int(link["user_id"]))
    if not record:
        return None
    if int(record.get("crypto_order_id") or 0) != int(crypto_order_id):
        return None
    return record


async def claim_for_fulfillment(user_id: int) -> dict[str, Any] | None:
    """Atomically claim pending/linked record for fulfillment (idempotency)."""
    redis = await get_redis()
    if redis is None:
        return None
    claim_key = build_direct_pay_claim_key(user_id)
    claimed = False
    try:
        claimed = bool(await redis.set(claim_key, "1", nx=True, ex=_claim_ttl_seconds()))
        if not claimed:
            return None
        raw = await redis.get(build_direct_pay_user_key(user_id))
        if not raw:
            await redis.delete(claim_key)
            return None
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get("status") not in ACTIVE_STATUSES:
            await redis.delete(claim_key)
            return None
        record["status"] = "fulfilling"
        record["updated_at"] = _now()
        await redis.set(
            build_direct_pay_user_key(user_id),
            json.dumps(record, ensure_ascii=False),
            ex=DIRECT_PAY_TTL_SECONDS,
        )
        return record
    except Exception as exc:
        logger.warning("direct_pay claim_for_fulfillment(%s): %s", user_id, exc)
        if claimed:
            with suppress(Exception):
                await redis.delete(claim_key)
        return None


async def mark_status(user_id: int, status: str) -> dict[str, Any] | None:
    record = await get_pending_for_user(user_id)
    if not record:
        return None
    record["status"] = status
    await _write_user_record(record)
    if status in {"fulfilled", "failed", "cancelled"}:
        await _clear_claim(user_id)
    return record


async def cancel_pending_for_user(user_id: int) -> dict[str, Any] | None:
    record = await get_pending_for_user(user_id)
    if not record:
        await _clear_claim(user_id)
        return None
    tx_id = record.get("transaction_id")
    crypto_id = record.get("crypto_order_id")
    if tx_id:
        await _delete_key(build_direct_pay_tx_key(int(tx_id)))
    if crypto_id:
        await _delete_key(build_direct_pay_crypto_key(int(crypto_id)))
    if record.get("status") in (*ACTIVE_STATUSES, "fulfilling"):
        record["status"] = "cancelled"
        await _write_user_record(record)
    await _clear_claim(user_id)
    return record


async def cancel_by_transaction_id(transaction_id: int) -> dict[str, Any] | None:
    record = await get_pending_by_transaction_id(transaction_id)
    if not record:
        return None
    return await cancel_pending_for_user(int(record["user_id"]))


async def cancel_by_crypto_order_id(crypto_order_id: int) -> dict[str, Any] | None:
    record = await get_pending_by_crypto_order_id(crypto_order_id)
    if not record:
        return None
    return await cancel_pending_for_user(int(record["user_id"]))


async def clear_pending(user_id: int) -> None:
    record = await get_pending_for_user(user_id)
    if record:
        tx_id = record.get("transaction_id")
        crypto_id = record.get("crypto_order_id")
        if tx_id:
            await _delete_key(build_direct_pay_tx_key(int(tx_id)))
        if crypto_id:
            await _delete_key(build_direct_pay_crypto_key(int(crypto_id)))
    await _delete_key(build_direct_pay_user_key(user_id))
    await _clear_claim(user_id)

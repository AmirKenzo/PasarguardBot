"""Redis-backed sticky discount codes applied via ``discount_CODE`` deep links."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.db.redis import get_redis
from app.logger import get_logger
from app.telegram.state.keys import get_redis_namespace
from app.utils.formatting.dates import Time_Date

logger = get_logger(__name__)

_DISCOUNT_PREFIX = "discount_"
_ALL_USERS_KEY_SUFFIX = "sticky_discount:all_users"


@dataclass(frozen=True)
class StickyDiscount:
    code: str
    discount_percentage: int
    expiration_date: int
    is_public: bool
    usage_limit: int
    times_used: int
    set_at: int


def _user_key(user_id: int) -> str:
    return f"{get_redis_namespace()}:sticky_discount:user:{user_id}"


def _code_index_key(code: str) -> str:
    return f"{get_redis_namespace()}:sticky_discount:code:{(code or '').upper()}"


def _all_users_key() -> str:
    return f"{get_redis_namespace()}:{_ALL_USERS_KEY_SUFFIX}"


def _ttl_seconds(expiration_date: int) -> int:
    remaining = int(expiration_date) - int(datetime.now().timestamp())
    return max(remaining, 60)


def _deserialize(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("code"):
            return data
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def parse_discount_start_param(param: str | None) -> str | None:
    """Parse ``discount_CODE`` deep links. Example: ``discount_PROMO`` -> ``PROMO``."""
    if not param:
        return None
    normalized = param.strip()
    if not normalized:
        return None
    if not normalized.lower().startswith(_DISCOUNT_PREFIX):
        return None
    code = normalized[len(_DISCOUNT_PREFIX) :].strip()
    return code.upper() if code else None


def is_discount_start_param(param: str | None) -> bool:
    return parse_discount_start_param(param) is not None


def discounted_price(price: int | float, discount_percentage: int) -> int:
    base = int(price)
    return int(base - (base * (int(discount_percentage) / 100)))


def _to_sticky(discount, *, set_at: int) -> StickyDiscount:
    return StickyDiscount(
        code=(discount.code or "").upper(),
        discount_percentage=int(discount.discount_percentage or 0),
        expiration_date=int(discount.expiration_date or 0),
        is_public=bool(discount.is_public),
        usage_limit=int(discount.usage_limit or 0),
        times_used=int(discount.times_used or 0),
        set_at=int(set_at),
    )


def _sticky_payload(discount, *, set_at: int) -> dict[str, Any]:
    return {
        "code": (discount.code or "").upper(),
        "discount_percentage": int(discount.discount_percentage or 0),
        "expiration_date": int(discount.expiration_date or 0),
        "is_public": bool(discount.is_public),
        "usage_limit": int(discount.usage_limit or 0),
        "times_used": int(discount.times_used or 0),
        "set_at": int(set_at),
    }


async def _remove_user_from_indexes(redis, user_id: int, code: str | None) -> None:
    await redis.srem(_all_users_key(), str(user_id))
    if code:
        await redis.srem(_code_index_key(code), str(user_id))


async def clear_sticky_discount(user_id: int, *, code: str | None = None) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        existing_code = code
        if not existing_code:
            raw = await redis.get(_user_key(user_id))
            if raw:
                data = _deserialize(raw)
                existing_code = data.get("code") if data else None
        await redis.delete(_user_key(user_id))
        await _remove_user_from_indexes(redis, user_id, existing_code)
    except Exception as exc:
        logger.warning("clear_sticky_discount(%s): %s", user_id, exc)


async def clear_sticky_for_code(code: str) -> int:
    """Remove a discount code from every user that had it sticky-applied."""
    redis = await get_redis()
    if redis is None or not code:
        return 0
    normalized = code.upper()
    index_key = _code_index_key(normalized)
    removed = 0
    try:
        members = await redis.smembers(index_key)
        for member in members or []:
            try:
                user_id = int(member)
            except (TypeError, ValueError):
                continue
            await redis.delete(_user_key(user_id))
            await redis.srem(_all_users_key(), str(user_id))
            removed += 1
        await redis.delete(index_key)
    except Exception as exc:
        logger.warning("clear_sticky_for_code(%s): %s", normalized, exc)
    return removed


async def _persist_sticky_payload(
    user_id: int,
    payload: dict[str, Any],
    *,
    previous_code: str | None = None,
) -> None:
    redis = await get_redis()
    if redis is None:
        raise RuntimeError("Redis unavailable")

    if previous_code and previous_code.upper() != payload["code"]:
        await _remove_user_from_indexes(redis, user_id, previous_code)

    await redis.set(
        _user_key(user_id),
        json.dumps(payload, ensure_ascii=False),
        ex=_ttl_seconds(int(payload["expiration_date"])),
    )
    await redis.sadd(_all_users_key(), str(user_id))
    await redis.sadd(_code_index_key(payload["code"]), str(user_id))


async def _read_sticky_payload(user_id: int) -> dict[str, Any] | None:
    redis = await get_redis()
    if redis is None:
        return None
    raw = await redis.get(_user_key(user_id))
    if not raw:
        return None
    return _deserialize(raw)


async def _refresh_sticky_payload(user_id: int, payload: dict[str, Any]) -> None:
    redis = await get_redis()
    if redis is None:
        return
    await redis.set(
        _user_key(user_id),
        json.dumps(payload, ensure_ascii=False),
        ex=_ttl_seconds(int(payload["expiration_date"])),
    )


async def get_sticky_discount(user_id: int) -> StickyDiscount | None:
    from app.db.crud.discount_codes import DiscountCodeManager

    try:
        data = await _read_sticky_payload(user_id)
        if not data:
            return None

        code = str(data["code"]).upper()
        status, discount = await DiscountCodeManager().validate_discount_code(code=code, user_id=user_id)
        if not status:
            await clear_sticky_discount(user_id, code=code)
            return None

        if not discount.expiration_date:
            await clear_sticky_discount(user_id, code=code)
            return None

        set_at = int(data.get("set_at") or int(datetime.now().timestamp()))
        sticky = _to_sticky(discount, set_at=set_at)
        await _refresh_sticky_payload(user_id, _sticky_payload(discount, set_at=sticky.set_at))
        return sticky
    except Exception as exc:
        logger.warning("get_sticky_discount(%s): %s", user_id, exc)
        return None


async def apply_sticky_discount(user_id: int, code: str) -> tuple[bool, str]:
    """Validate and persist a sticky discount. Returns ``(success, message)``."""
    from app.db.crud.discount_codes import DiscountCodeManager

    normalized = (code or "").strip().upper()
    if not normalized:
        return False, "کد تخفیف نامعتبر است."

    status, discount = await DiscountCodeManager().validate_discount_code(code=normalized, user_id=user_id)
    if not status:
        return False, str(discount)

    if not discount.expiration_date:
        return False, "فقط کدهای تخفیف موقت (دارای تاریخ انقضا) از طریق لینک قابل فعال‌سازی هستند."

    existing = await get_sticky_discount(user_id)
    if existing and existing.code == normalized:
        return True, "already_applied"

    now = int(datetime.now().timestamp())
    await _persist_sticky_payload(
        user_id,
        _sticky_payload(discount, set_at=now),
        previous_code=existing.code if existing else None,
    )
    return True, "applied"


def build_discount_deep_link(bot_username: str, code: str) -> str:
    username = (bot_username or "bot").lstrip("@")
    normalized = (code or "").upper()
    return f"https://t.me/{username}?start=discount_{normalized}"


def format_discount_deep_links_text(bot_username: str, code: str) -> str:
    link = build_discount_deep_link(bot_username, code)
    return f"🔗 **لینک دیپ کد تخفیف:**\n`{link}`"


def format_sticky_applied_message(sticky: StickyDiscount) -> str:
    expiration = Time_Date(sticky.expiration_date)
    visibility = "🌍 عمومی" if sticky.is_public else "💎 پرایوت"
    usage_line = ""
    if not sticky.is_public:
        usage_line = f"🔢 **تعداد استفاده:** `{sticky.times_used}`/`{sticky.usage_limit}`\n"
    return (
        "🎉 **کد تخفیف روی حساب شما فعال شد!**\n\n"
        f"🎟 **کد:** `{sticky.code}`\n"
        f"💸 **درصد تخفیف:** `{sticky.discount_percentage}%`\n"
        f"📋 **نوع:** {visibility}\n"
        f"⏳ **اعتبار تا:** `{expiration['jf']}` ({expiration['remaining_days']})\n"
        f"{usage_line}\n"
        "✅ از این به بعد قیمت‌ها با این تخفیف محاسبه می‌شوند و نیازی به وارد کردن مجدد کد نیست."
    )


def format_profile_sticky_discount(sticky: StickyDiscount, bot_username: str) -> str:
    expiration = Time_Date(sticky.expiration_date)
    link = build_discount_deep_link(bot_username, sticky.code)
    return (
        "\n"
        "━━━━━━━━ 🎟 **کد تخفیف فعال (موقت)** ━━━━━━━━\n"
        f"**📌 کد:** `{sticky.code}`\n"
        f"**💸 درصد:** `{sticky.discount_percentage}%`\n"
        f"**⏳ انقضا:** `{expiration['jf']}` ({expiration['remaining_days']})\n"
        f"**🔗 لینک دعوت دیگران:**\n`{link}`\n"
    )


async def count_sticky_assigned_users() -> int:
    redis = await get_redis()
    if redis is None:
        return 0
    try:
        return int(await redis.scard(_all_users_key()) or 0)
    except Exception as exc:
        logger.warning("count_sticky_assigned_users: %s", exc)
        return 0


async def count_sticky_users_for_code(code: str) -> int:
    redis = await get_redis()
    if redis is None or not code:
        return 0
    try:
        return int(await redis.scard(_code_index_key(code)) or 0)
    except Exception as exc:
        logger.warning("count_sticky_users_for_code(%s): %s", code, exc)
        return 0


async def get_sticky_assignment_stats() -> dict[str, int]:
    """Return ``{CODE: assigned_user_count}`` for admin stats."""
    redis = await get_redis()
    if redis is None:
        return {}
    pattern = f"{get_redis_namespace()}:sticky_discount:code:*"
    stats: dict[str, int] = {}
    try:
        async for key in redis.scan_iter(match=pattern, count=200):
            code = str(key).rsplit(":", 1)[-1]
            stats[code] = int(await redis.scard(key) or 0)
    except Exception as exc:
        logger.warning("get_sticky_assignment_stats: %s", exc)
    return stats

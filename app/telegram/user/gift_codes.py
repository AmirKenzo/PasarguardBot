"""Temporary wallet gift codes kept only in Redis (at most 24 hours): admin /gift, /gifts, /delgift and user /redeem."""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass

from telethon import events

from app.db.crud.user import update_Money
from app.db.redis import get_redis
from app.logger import LogType, get_logger
from app.telegram.plugins import PluginContext
from app.telegram.shared.url_presets import get_bot_username
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state.keys import get_redis_namespace
from config import ADMIN_ID

MODULE_NAME = "user.gift_codes"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Temporary wallet gift codes stored in Redis"

logger = get_logger(__name__)

MAX_TTL_HOURS = 24
MAX_USES = 100_000
GENERATED_CODE_LEN = 10
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{4,32}$")
ATTEMPT_LIMIT = 5
ATTEMPT_WINDOW_SECS = 60
GIFT_START_PREFIX = "gift_"

# Claims one use of a code for a user atomically.
# Returns {0} missing/expired, {1} already used, {2} no uses left, {3, amount} claimed.
REDEEM_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then return {0} end
if redis.call('SISMEMBER', KEYS[2], ARGV[1]) == 1 then return {1} end
local max_uses = tonumber(redis.call('HGET', KEYS[1], 'max_uses'))
if redis.call('SCARD', KEYS[2]) >= max_uses then return {2} end
redis.call('SADD', KEYS[2], ARGV[1])
local ttl = redis.call('PTTL', KEYS[1])
if ttl > 0 then redis.call('PEXPIRE', KEYS[2], ttl) end
return {3, tonumber(redis.call('HGET', KEYS[1], 'amount'))}
"""

REDIS_UNAVAILABLE_TEXT = "⚠️ سیستم کد هدیه در حال حاضر در دسترس نیست. کمی بعد دوباره امتحان کنید."
REDEEM_USAGE_TEXT = "🎁 برای استفاده از کد هدیه بنویسید:\n`/redeem CODE`"
ADMIN_USAGE_TEXT = (
    "🎁 **ساخت کد هدیه**\n\n"
    "`/gift مبلغ تعداد ساعت [کد]`\n"
    "مثال: `/gift 50000 100 24 NOROOZ`\n\n"
    "• ساعت بین 1 تا 24 است و بعد از آن کد خود به خود پاک می شود.\n"
    "• اگر کد را ننویسید، یک کد تصادفی ساخته می شود.\n"
    "• بعد از ساخت، لینک آماده اشتراک گذاری هم برایتان ارسال می شود.\n\n"
    "`/gifts` لیست کدهای فعال با لینک اشتراک گذاری\n"
    "`/delgift کد` حذف کد"
)


def _code_key(code: str) -> str:
    return f"{get_redis_namespace()}:gift:code:{code}"


def _used_key(code: str) -> str:
    return f"{get_redis_namespace()}:gift:used:{code}"


def _index_key() -> str:
    return f"{get_redis_namespace()}:gift:index"


def _attempts_key(user_id: int) -> str:
    return f"{get_redis_namespace()}:gift:attempts:{user_id}"


def _normalize_code(raw: str | None) -> str | None:
    """Uppercase a code and accept only ``[A-Z0-9_-]{4,32}``, so it is safe inside a Redis key."""
    code = (raw or "").strip().upper()
    return code if CODE_PATTERN.fullmatch(code) else None


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(GENERATED_CODE_LEN))


def _command_args(event) -> list[str]:
    return (event.raw_text or "").split()[1:]


def _format_remaining(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return f"{hours} ساعت و {minutes} دقیقه" if hours > 0 else f"{minutes} دقیقه"


async def _allow_attempt(redis, user_id: int) -> bool:
    """Count a redeem attempt; False once the user exceeds the per-minute limit."""
    key = _attempts_key(user_id)
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, ATTEMPT_WINDOW_SECS)
    except Exception as exc:
        logger.warning("Gift code attempt counter failed: %s", exc)
        return True
    return count <= ATTEMPT_LIMIT


async def redeem_for_user(user_id: int, code: str) -> str:
    """Claim a code for a user and credit the wallet; returns the text to show the user."""
    redis = await get_redis()
    if redis is None:
        return REDIS_UNAVAILABLE_TEXT
    if not await _allow_attempt(redis, user_id):
        return "⏳ تعداد تلاش های شما زیاد بود. یک دقیقه دیگر دوباره امتحان کنید."

    try:
        result = await redis.eval(REDEEM_SCRIPT, 2, _code_key(code), _used_key(code), str(user_id))
    except Exception as exc:
        logger.warning("Gift code redeem failed for %s: %s", user_id, exc)
        return REDIS_UNAVAILABLE_TEXT

    status = int(result[0]) if result else 0
    if status == 1:
        return "⚠️ شما قبلاً از این کد هدیه استفاده کرده اید."
    if status == 2:
        return "😔 ظرفیت این کد هدیه تمام شده است."
    if status != 3:
        return "❌ این کد هدیه وجود ندارد یا منقضی شده است."

    amount = int(result[1])
    try:
        new_balance = await update_Money(user_id=user_id, Money=amount)
    except Exception as exc:
        logger.warning("Gift code credit failed for %s: %s", user_id, exc)
        new_balance = None
    if new_balance is None:
        try:
            await redis.srem(_used_key(code), str(user_id))
        except Exception as exc:
            logger.warning("Gift code rollback failed for %s: %s", user_id, exc)
        return "⚠️ شارژ کیف پول انجام نشد. لطفاً دوباره امتحان کنید."

    await send_log_message(
        LogType.OTHER,
        message=(
            f"🎁 کاربر `{user_id}` کد هدیه `{code}` را استفاده کرد و {amount:,} تومان شارژ شد.\n"
            f"💳 موجودی جدید: {int(new_balance):,} تومان"
        ),
    )
    return (
        f"🎉 کد هدیه با موفقیت اعمال شد!\n\n"
        f"💰 مبلغ {amount:,} تومان به کیف پول شما اضافه شد.\n"
        f"💳 موجودی جدید: {int(new_balance):,} تومان"
    )


def parse_gift_start_param(param: str | None) -> str | None:
    """Extract the code from a ``gift_<CODE>`` start parameter."""
    param = (param or "").strip()
    if not param.lower().startswith(GIFT_START_PREFIX):
        return None
    return _normalize_code(param[len(GIFT_START_PREFIX) :])


async def _gift_link(client, code: str) -> str | None:
    """Share link that redeems the code through the bot's start parameter."""
    username = (await get_bot_username(client) or "").strip().lstrip("@")
    return f"https://t.me/{username}?start={GIFT_START_PREFIX}{code}" if username else None


@bot_is_offline
async def redeem_command(event) -> None:
    if not event.is_private:
        return
    args = _command_args(event)
    code = _normalize_code(args[0]) if args else None
    if code is None:
        await event.reply(REDEEM_USAGE_TEXT)
        raise events.StopPropagation
    await event.reply(await redeem_for_user(event.sender_id, code))
    raise events.StopPropagation


@dataclass(frozen=True)
class NewGift:
    amount: int
    max_uses: int
    hours: int
    code: str | None


def _parse_new_gift(args: list[str]) -> NewGift | str:
    """Parse ``amount uses hours [code]``; returns an error text when invalid."""
    if len(args) < 3:
        return ADMIN_USAGE_TEXT
    try:
        amount = int(args[0].replace(",", ""))
    except ValueError:
        return "❌ مبلغ نامعتبر است."
    try:
        max_uses = int(args[1])
    except ValueError:
        return "❌ تعداد استفاده نامعتبر است."
    try:
        hours = int(args[2])
    except ValueError:
        return "❌ تعداد ساعت نامعتبر است."
    if amount <= 0:
        return "❌ مبلغ باید بیشتر از صفر باشد."
    if not 1 <= max_uses <= MAX_USES:
        return "❌ تعداد استفاده باید بین 1 تا 100000 باشد."
    if not 1 <= hours <= MAX_TTL_HOURS:
        return "❌ مدت اعتبار باید بین 1 تا 24 ساعت باشد."
    code = None
    if len(args) > 3:
        code = _normalize_code(args[3])
        if code is None:
            return "❌ کد باید 4 تا 32 کاراکتر و فقط شامل حروف انگلیسی، عدد، - و _ باشد."
    return NewGift(amount=amount, max_uses=max_uses, hours=hours, code=code)


async def create_gift(event) -> None:
    if not event.is_private:
        return
    gift = _parse_new_gift(_command_args(event))
    if isinstance(gift, str):
        await event.reply(gift)
        raise events.StopPropagation

    redis = await get_redis()
    if redis is None:
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation

    code = gift.code or _generate_code()
    ttl = gift.hours * 3600
    expires_at = int(time.time()) + ttl
    key = _code_key(code)
    try:
        created = await redis.hsetnx(key, "amount", gift.amount)
    except Exception as exc:
        logger.warning("Gift code create failed: %s", exc)
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation from None
    if not created:
        await event.reply("⚠️ این کد هم اکنون فعال است. کد دیگری انتخاب کنید.")
        raise events.StopPropagation

    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={"max_uses": gift.max_uses, "expires_at": expires_at, "created_by": event.sender_id})
            pipe.expire(key, ttl)
            pipe.delete(_used_key(code))
            pipe.zadd(_index_key(), {code: expires_at})
            await pipe.execute()
    except Exception as exc:
        logger.warning("Gift code store failed: %s", exc)
        try:
            await redis.delete(key)
        except Exception:
            logger.debug("Gift code cleanup failed for %s", code)
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation from None

    link = await _gift_link(event.client, code)
    link_text = (
        f"\n\n🔗 لینک اشتراک گذاری (با یک کلیک کد اعمال می شود):\n`{link}`\n\n"
        "📢 این لینک را در کانال، گروه یا پیام برای کاربران بفرستید. هر کس روی آن بزند ربات باز می شود "
        "و مبلغ همان لحظه به کیف پولش اضافه می شود (کاربران جدید هم اول ثبت نام می شوند)."
        if link
        else ""
    )
    await event.reply(
        f"✅ کد هدیه ساخته شد.\n\n"
        f"🎁 کد: `{code}`\n"
        f"💰 مبلغ: {gift.amount:,} تومان\n"
        f"👥 تعداد استفاده: {gift.max_uses:,}\n"
        f"⏳ اعتبار: {gift.hours} ساعت"
        f"{link_text}\n\n"
        f"⌨️ یا کاربران این دستور را در ربات بفرستند:\n`/redeem {code}`"
    )
    raise events.StopPropagation


async def list_gifts(event) -> None:
    if not event.is_private:
        return
    redis = await get_redis()
    if redis is None:
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation

    now = int(time.time())
    lines: list[str] = []
    try:
        await redis.zremrangebyscore(_index_key(), "-inf", now)
        codes = await redis.zrange(_index_key(), 0, -1)
        for code in codes:
            amount, max_uses, expires_at = await redis.hmget(_code_key(code), "amount", "max_uses", "expires_at")
            if amount is None or max_uses is None or expires_at is None:
                await redis.zrem(_index_key(), code)
                continue
            used = await redis.scard(_used_key(code))
            link = await _gift_link(event.client, code)
            link_line = f"\n🔗 `{link}`" if link else ""
            lines.append(
                f"🎁 `{code}`\n"
                f"💰 {int(amount):,} تومان | 👥 {used}/{int(max_uses)} | ⏳ {_format_remaining(int(expires_at) - now)}"
                f"{link_line}"
            )
    except Exception as exc:
        logger.warning("Gift code list failed: %s", exc)
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation from None

    text = "🎁 **کدهای هدیه فعال**\n\n" + "\n\n".join(lines) if lines else "📭 هیچ کد هدیه فعالی وجود ندارد."
    await event.reply(text)
    raise events.StopPropagation


async def delete_gift(event) -> None:
    if not event.is_private:
        return
    args = _command_args(event)
    code = _normalize_code(args[0]) if args else None
    if code is None:
        await event.reply("🗑 برای حذف بنویسید:\n`/delgift CODE`")
        raise events.StopPropagation

    redis = await get_redis()
    if redis is None:
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation
    try:
        removed = await redis.delete(_code_key(code), _used_key(code))
        await redis.zrem(_index_key(), code)
    except Exception as exc:
        logger.warning("Gift code delete failed: %s", exc)
        await event.reply(REDIS_UNAVAILABLE_TEXT)
        raise events.StopPropagation from None

    await event.reply(f"🗑 کد هدیه `{code}` حذف شد." if removed else "❌ این کد هدیه پیدا نشد.")
    raise events.StopPropagation


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(redeem_command, events.NewMessage(incoming=True, pattern=r"^/redeem(?:\s|$)"))
    kenzo.add_event_handler(
        create_gift, events.NewMessage(incoming=True, pattern=r"^/gift(?:\s|$)", from_users=ADMIN_ID)
    )
    kenzo.add_event_handler(list_gifts, events.NewMessage(incoming=True, pattern=r"^/gifts$", from_users=ADMIN_ID))
    kenzo.add_event_handler(
        delete_gift, events.NewMessage(incoming=True, pattern=r"^/delgift(?:\s|$)", from_users=ADMIN_ID)
    )

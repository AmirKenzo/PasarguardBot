"""Bot maintenance / offline mode — no app.telegram imports (avoids circular imports)."""

from __future__ import annotations

import asyncio
import contextlib
import time
from functools import wraps

from sqlalchemy.future import select
from telethon import Button

from app.db.base import AsyncSessionLocal as Session
from app.db.models.settings import Settings
from config import ADMIN_ID, ADMIN_ID_TAG

BOT_OFFLINE_MESSAGE = (
    "🛠️ ربات به‌صورت موقت در دسترس نیست\n\n"
    "⚙️ در حال انجام بروزرسانی و بهینه‌سازی هستیم\n"
    "⏳ لطفاً چند دقیقه بعد دوباره تلاش کنید"
)
BOT_OFFLINE_ALERT = "🛠️ ربات موقتاً در دسترس نیست. لطفاً چند دقیقه بعد تلاش کنید."

user_offline_notified: dict[str, float] = {}
offline_notification_lock = asyncio.Lock()


def prune_offline_notifications(now: float | None = None, *, max_age_seconds: float = 600.0) -> int:
    """Drop offline-notice markers older than ``max_age_seconds``. Returns entries removed."""
    now = now if now is not None else time.time()
    stale = [k for k, v in user_offline_notified.items() if now - v > max_age_seconds]
    for k in stale:
        user_offline_notified.pop(k, None)
    return len(stale)


def _is_private_chat(update) -> bool:
    if getattr(update, "is_channel", False):
        return False
    if getattr(update, "is_group", False):
        return False
    return bool(getattr(update, "is_private", False))


def _offline_notification_event_id(update) -> int | None:
    if getattr(update, "id", None) is not None:
        return update.id
    if hasattr(update, "message") and getattr(update.message, "id", None) is not None:
        return update.message.id
    if hasattr(update, "msg_id"):
        return update.msg_id
    return None


async def _clear_offline_notifications(user_id: int) -> None:
    async with offline_notification_lock:
        keys_to_delete = [k for k in user_offline_notified if k.startswith(f"{user_id}_") or k == str(user_id)]
        for k in keys_to_delete:
            user_offline_notified.pop(k, None)


async def _notify_bot_offline(update) -> None:
    user_id = update.sender_id
    event_id = _offline_notification_event_id(update)
    notification_key = f"{user_id}_{event_id}" if event_id else str(user_id)

    should_send = False
    async with offline_notification_lock:
        if notification_key not in user_offline_notified:
            user_offline_notified[notification_key] = time.time()
            should_send = True
            now = time.time()
            keys_to_delete = [k for k, v in user_offline_notified.items() if now - v > 600]
            for k in keys_to_delete:
                user_offline_notified.pop(k, None)

    is_callback = hasattr(update, "data")
    if is_callback:
        try:
            if should_send:
                alert_text = BOT_OFFLINE_MESSAGE if len(BOT_OFFLINE_MESSAGE) <= 200 else BOT_OFFLINE_ALERT
                await update.answer(alert_text, alert=True)
            else:
                await update.answer()
        except Exception:
            pass
        return

    if not should_send:
        return

    offline_buttons = [Button.url(text="📢 وضعیت بروزرسانی", url=f"https://t.me/{ADMIN_ID_TAG}")]
    with contextlib.suppress(Exception):
        await update.reply(BOT_OFFLINE_MESSAGE, buttons=offline_buttons)


async def block_if_bot_offline(update) -> bool:
    """
    Block non-admin users when bot_mode is off.
    Returns True if the update must not be processed further.
    """
    user_id = update.sender_id
    if not user_id or user_id in ADMIN_ID:
        return False

    async with Session() as session:
        result = await session.execute(select(Settings).filter_by(id=1))
        bot_status = result.scalars().first()

    if not bot_status or bot_status.bot_mode != 0:
        await _clear_offline_notifications(user_id)
        return False

    if not _is_private_chat(update):
        return True

    await _notify_bot_offline(update)
    return True


def bot_is_offline(handler):
    """English docstring for bot_is_offline."""

    @wraps(handler)
    async def decorated(update, *args, **kwargs):
        if await block_if_bot_offline(update):
            return None
        return await handler(update, *args, **kwargs)

    return decorated

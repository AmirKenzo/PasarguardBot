from __future__ import annotations

import random
import time
from functools import wraps

from app.telegram.shared.utils.antispam_state import (
    ANTI_SPAM_TEXT,
    antispam_lock,
    user_blocked_until,
    user_last_event_id,
    user_last_message_time,
    user_spam_events,
)
from config import ADMIN_ID


def antispam(seconds_block=10, min_interval=0.8):
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            from_id = event.sender_id
            now = time.time()

            if not event.is_private:
                return await func(event, *args, **kwargs)

            if from_id:
                if from_id in ADMIN_ID:
                    return await func(event, *args, **kwargs)

                is_spam = False
                spam_message = None
                should_notify = False

                async with antispam_lock:
                    if user_blocked_until.get(from_id, 0) > now:
                        return None

                    event_id = None
                    if getattr(event, "id", None) is not None:
                        event_id = event.id
                    elif hasattr(event, "message") and getattr(event.message, "id", None) is not None:
                        event_id = event.message.id

                    if event_id is not None:
                        spam_event_key = f"{from_id}_{event_id}"
                        if spam_event_key in user_spam_events:
                            return None

                    last_time = user_last_message_time.get(from_id, 0)

                    if (now - last_time) < min_interval:
                        user_blocked_until[from_id] = now + seconds_block
                        spam_message = random.choice(ANTI_SPAM_TEXT).format(seconds_block=seconds_block)
                        is_spam = True
                        if event_id is not None:
                            spam_event_key = f"{from_id}_{event_id}"
                            user_spam_events[spam_event_key] = now
                            should_notify = True
                            keys_to_delete = [k for k, v in user_spam_events.items() if now - v > 60]
                            for key in keys_to_delete:
                                user_spam_events.pop(key, None)
                    else:
                        if event_id is not None:
                            last_event_id = user_last_event_id.get(from_id)
                            if last_event_id == event_id:
                                user_last_message_time[from_id] = now
                                return await func(event, *args, **kwargs)

                        user_last_message_time[from_id] = now
                        if event_id is not None:
                            user_last_event_id[from_id] = event_id

                if is_spam and should_notify:
                    try:
                        await event.answer(spam_message, alert=True)
                    except Exception:
                        await event.reply(spam_message)

                if is_spam:
                    return None

            return await func(event, *args, **kwargs)

        return wrapper

    return decorator


_last_callback_time: dict[int, float] = {}
_debounce_seconds = 0.01


def prune_callback_debounce(now: float | None = None, *, idle_seconds: float = 60.0) -> int:
    """Drop debounce timestamps older than any debounce window. Returns entries removed."""
    now = now if now is not None else time.time()
    stale = [uid for uid, t in _last_callback_time.items() if now - t > idle_seconds]
    for uid in stale:
        _last_callback_time.pop(uid, None)
    return len(stale)


def debounce_callback(seconds: float = _debounce_seconds):
    """Prevent duplicate CallbackQuery handler execution in a short interval."""

    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            user_id = event.sender_id
            now = time.time()
            last_time = _last_callback_time.get(user_id, 0)
            if now - last_time < seconds:
                if hasattr(event, "answer"):
                    await event.answer(cache_time=0)
                return None
            _last_callback_time[user_id] = now
            return await func(event, *args, **kwargs)

        return wrapper

    return decorator

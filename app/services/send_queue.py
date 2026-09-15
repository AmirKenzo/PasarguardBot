"""Redis send queue: enqueue jobs, worker sends one-by-one with delay + FloodWait backoff."""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time
from typing import Any

from telethon.errors import FloodWaitError, InputUserDeactivatedError, UserIsBlockedError
from telethon.tl import functions, types

from app import Kenzo
from app.db.crud.log_channels import LogChannelManager
from app.db.crud.user import set_user_status
from app.db.redis import get_redis
from app.logger import LogTag, get_logger
from app.services.broadcast.markup import deserialize_buttons, serialize_reply_markup
from app.services.telegram.rich_message import prepare_rich_markdown
from app.telegram.state.keys import get_redis_namespace
from config import LOG_CHANNEL, SEND_QUEUE_DELAY_SEC, SEND_QUEUE_ENABLED, SEND_QUEUE_MAX_LEN

logger = get_logger(__name__)

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_flood_threshold_ready = False


def queue_key() -> str:
    return f"{get_redis_namespace()}:send_queue"


def _ensure_flood_threshold() -> None:
    """Disable Telethon auto-sleep once; never mutate around each send."""
    global _flood_threshold_ready
    if _flood_threshold_ready:
        return
    Kenzo.flood_sleep_threshold = 0
    _flood_threshold_ready = True


def _dump_buttons(buttons: Any) -> list[list[dict]] | None:
    if not buttons:
        return None
    if isinstance(buttons, list) and buttons and buttons[0] and isinstance(buttons[0][0], dict):
        return serialize_reply_markup(buttons)
    try:
        return serialize_reply_markup(Kenzo.build_reply_markup(buttons))
    except Exception:
        return serialize_reply_markup(buttons)


def _prepare_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        if key == "buttons":
            out[key] = _dump_buttons(value)
        elif key == "file" and not isinstance(value, (str, int)):
            path = getattr(value, "name", None) or getattr(value, "path", None)
            if not path:
                raise TypeError("file must be a path/URL string (use Kenzo.send_file for media bytes)")
            out[key] = str(path)
        else:
            out[key] = value
    return out


def _text(kwargs: dict[str, Any]) -> str:
    for key in ("message", "text", "caption"):
        if kwargs.get(key) is not None:
            return str(kwargs[key])
    return ""


def _job_summary(job: dict[str, Any], kwargs: dict[str, Any]) -> str:
    parts = [
        f"To={kwargs.get('entity')}",
        f"Type={job.get('log_type') or '-'}",
    ]
    enqueued_at = job.get("enqueued_at")
    if isinstance(enqueued_at, (int, float)):
        parts.append(f"Queued={max(0.0, time.time() - float(enqueued_at)):.1f}s")
    return " | ".join(parts)


def _apply_parse_mode(send_kwargs: dict[str, Any], text: str) -> None:
    mode = send_kwargs.get("parse_mode")
    if mode == "rich":
        return
    needs_custom = "](emoji/" in text or "tg://emoji?id=" in text
    if needs_custom or (isinstance(mode, str) and mode.lower() in ("md", "markdown")):
        send_kwargs["parse_mode"] = Kenzo.parse_mode


async def _send(kwargs: dict[str, Any]) -> None:
    buttons = deserialize_buttons(kwargs.pop("buttons", None))
    mode = kwargs.get("parse_mode")
    entity = int(kwargs["entity"])
    text = _text(kwargs)

    if mode == "rich":
        reply_to = kwargs.get("reply_to")
        req: dict[str, Any] = {
            "peer": entity,
            "message": "",
            "rich_message": types.InputRichMessageMarkdown(
                prepare_rich_markdown(text),
                rtl=bool(kwargs.get("rtl", True)),
                noautolink=bool(kwargs.get("noautolink", True)),
            ),
            "reply_markup": Kenzo.build_reply_markup(buttons) if buttons else None,
            "random_id": random.getrandbits(63),
        }
        if reply_to is not None:
            req["reply_to"] = types.InputReplyToMessage(reply_to_msg_id=int(reply_to))
        await Kenzo(functions.messages.SendMessageRequest(**req))
        return

    send_kwargs = {k: v for k, v in kwargs.items() if k not in ("rtl", "noautolink", "text") and v is not None}
    if buttons is not None:
        send_kwargs["buttons"] = buttons
    _apply_parse_mode(send_kwargs, text)
    if "file" in send_kwargs:
        await Kenzo.send_file(**send_kwargs)
    else:
        await Kenzo.send_message(**send_kwargs)


async def _resolve_log_entity(log_type: str, kwargs: dict[str, Any]) -> dict[str, Any] | None:
    dest = await LogChannelManager().get_log_channel_destination(str(log_type))
    if dest:
        kwargs["entity"] = int(dest["chat_id"])
        if dest.get("topic_id") and "reply_to" not in kwargs:
            kwargs["reply_to"] = int(dest["topic_id"])
        return kwargs
    if LOG_CHANNEL is not None:
        kwargs["entity"] = LOG_CHANNEL
        return kwargs
    return None


async def _requeue(job: dict[str, Any], *, delay_seconds: float) -> None:
    job = dict(job)
    job["not_before"] = time.time() + max(float(delay_seconds), 0.0)
    job["flood_attempts"] = int(job.get("flood_attempts") or 0) + 1
    redis = await get_redis()
    if not redis:
        return
    try:
        key = queue_key()
        await redis.lpush(key, json.dumps(job, ensure_ascii=False, default=str))
        max_len = max(int(SEND_QUEUE_MAX_LEN), 1)
        await redis.ltrim(key, 0, max_len - 1)
    except Exception as exc:
        logger.warning("send_queue requeue failed: %s", exc)


async def _deliver(job: dict[str, Any]) -> None:
    _ensure_flood_threshold()
    kwargs = dict(job.get("kwargs") or {})
    log_type = job.get("log_type")
    try:
        if log_type:
            resolved = await _resolve_log_entity(str(log_type), kwargs)
            if not resolved:
                logger.debug("No log channel for %s — skip", log_type)
                return
            kwargs = resolved
        elif kwargs.get("entity") is None:
            logger.error("send_queue job missing entity")
            return

        try:
            await _send(kwargs)
            logger.info("%s send_queue | %s", LogTag.REDIS, _job_summary(job, kwargs))
        except FloodWaitError as exc:
            attempts = int(job.get("flood_attempts") or 0) + 1
            logger.info(
                "%s send_queue FloodWait %ss | entity=%s attempt=%s/3 — requeue",
                LogTag.REDIS,
                exc.seconds,
                kwargs.get("entity"),
                attempts,
            )
            if attempts >= 3:
                logger.error(
                    "%s send_queue FloodWait exhausted | entity=%s",
                    LogTag.REDIS,
                    kwargs.get("entity"),
                )
                return
            await _requeue(job, delay_seconds=float(exc.seconds) + 1.0)
        except InputUserDeactivatedError:
            entity = kwargs.get("entity")
            if entity is not None:
                await set_user_status(int(entity), "DeleteAccount")
        except UserIsBlockedError:
            entity = kwargs.get("entity")
            if entity is not None:
                await set_user_status(int(entity), "BlockedBot")
    except Exception as exc:
        logger.error(
            "%s send_queue send failed | entity=%s err=%s: %s",
            LogTag.REDIS,
            kwargs.get("entity"),
            type(exc).__name__,
            exc,
        )


async def enqueue(
    message: str | None = None,
    *,
    entity: int | str | None = None,
    log_type: str | Any | None = None,
    **kwargs: Any,
) -> bool:
    """
    Save one outgoing message to Redis. Worker sends later (1 per SEND_QUEUE_DELAY_SEC).

    Pass entity=chat_id or log_type=... (admin log channel/topic).
    For photo/bytes receipts use Kenzo.send_file directly — do not queue media blobs.
    Supports: message, file (path/URL only), caption, parse_mode,
    buttons, link_preview, reply_to, rtl, noautolink.
    Premium emoji: ``[✅](emoji/DOCUMENT_ID)``
    """
    if entity is None and log_type is None:
        raise ValueError("enqueue requires entity=... or log_type=...")

    payload = dict(kwargs)
    if message is not None:
        payload["message"] = message

    try:
        prepared = _prepare_kwargs(payload)
    except Exception as exc:
        logger.warning("%s send_queue prepare failed: %s", LogTag.REDIS, exc)
        return False

    job: dict[str, Any] = {"v": 1, "enqueued_at": time.time()}
    if log_type is not None:
        if hasattr(log_type, "value"):
            log_type = log_type.value
        job["log_type"] = str(log_type)
        job["kwargs"] = prepared
    else:
        prepared["entity"] = int(entity)  # type: ignore[arg-type]
        job["kwargs"] = prepared

    redis = await get_redis()
    if not redis or not SEND_QUEUE_ENABLED:
        # Queueing (throttling/FloodWait backoff) is only available with Redis;
        # without it, send right away instead of silently dropping the message.
        logger.debug("send_queue unavailable — sending directly: %s", job.get("log_type") or "entity")
        await _deliver(job)
        return True
    try:
        key = queue_key()
        await redis.lpush(key, json.dumps(job, ensure_ascii=False, default=str))
        max_len = max(int(SEND_QUEUE_MAX_LEN), 1)
        await redis.ltrim(key, 0, max_len - 1)
        return True
    except Exception as exc:
        logger.warning("send_queue lpush failed: %s", exc)
        return False


async def _worker_loop(stop_event: asyncio.Event) -> None:
    key = queue_key()
    delay = max(float(SEND_QUEUE_DELAY_SEC), 0.0)
    logger.info("%s send_queue worker | key=%s delay=%.2fs", LogTag.REDIS, key, delay)
    _ensure_flood_threshold()

    while not stop_event.is_set():
        redis = await get_redis()
        if not redis:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            continue

        try:
            result = await redis.brpop(key, timeout=2)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("%s send_queue brpop: %s", LogTag.REDIS, exc)
            await asyncio.sleep(1)
            continue

        if not result:
            continue

        try:
            job = json.loads(result[1])
        except json.JSONDecodeError:
            continue

        if isinstance(job, dict):
            not_before = job.get("not_before")
            if isinstance(not_before, (int, float)) and float(not_before) > time.time():
                # Keep the queue moving: push deferred job back unchanged and continue.
                try:
                    await redis.rpush(key, json.dumps(job, ensure_ascii=False, default=str))
                    max_len = max(int(SEND_QUEUE_MAX_LEN), 1)
                    await redis.ltrim(key, 0, max_len - 1)
                except Exception as exc:
                    logger.warning("%s send_queue defer push: %s", LogTag.REDIS, exc)
                wait_for = min(max(0.05, float(not_before) - time.time()), 1.0)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=wait_for)
                continue
            await _deliver(job)

        if delay > 0 and not stop_event.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=delay)

    logger.info("%s send_queue worker stopped", LogTag.REDIS)


def _on_worker_done(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("%s send_queue worker CRASHED: %s", LogTag.REDIS, exc, exc_info=exc)


def start_send_queue_worker() -> None:
    global _worker_task, _stop_event
    if not SEND_QUEUE_ENABLED:
        return
    if _worker_task is not None and not _worker_task.done():
        return
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop(_stop_event), name="send_queue_worker")
    _worker_task.add_done_callback(_on_worker_done)


async def stop_send_queue_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    task = _worker_task
    _worker_task = None
    _stop_event = None
    if task is None:
        return
    task.remove_done_callback(_on_worker_done)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

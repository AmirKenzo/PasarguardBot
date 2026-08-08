"""Redis state for Telegram bot — two things only: step and data."""

from __future__ import annotations

import json
import time
from typing import Any

from app.db.redis import get_redis
from app.logger import get_logger
from app.logger.tags import LogTag
from app.telegram.state.keys import build_cache_key, build_state_key
from config import STATE_TTL_SECONDS

logger = get_logger(__name__)

_STEP_FIELD = "_current"

# Short process-local cache so dozens of NewMessage filters in one update
# share a single Redis round-trip (Telethon evaluates every handler filter).
_STEP_LOCAL_TTL_SEC = 1.5
_step_local: dict[int, tuple[float, str | None]] = {}


def _invalidate_step_local(user_id: int) -> None:
    _step_local.pop(user_id, None)


def _get_step_local(user_id: int) -> tuple[bool, str | None]:
    entry = _step_local.get(user_id)
    if entry is None:
        return False, None
    ts, value = entry
    if time.monotonic() - ts > _STEP_LOCAL_TTL_SEC:
        _step_local.pop(user_id, None)
        return False, None
    return True, value


def _set_step_local(user_id: int, value: str | None) -> None:
    _step_local[user_id] = (time.monotonic(), value)
    if len(_step_local) > 10_000:
        now = time.monotonic()
        stale = [uid for uid, (t, _) in _step_local.items() if now - t > _STEP_LOCAL_TTL_SEC]
        for uid in stale:
            _step_local.pop(uid, None)


def _serialize(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _deserialize(raw: str) -> Any:
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except TypeError, ValueError, json.JSONDecodeError:
        return raw


async def _refresh_ttl(redis, hash_key: str, ttl: int | None) -> None:
    seconds = ttl if ttl is not None else STATE_TTL_SECONDS
    if seconds > 0:
        await redis.expire(hash_key, seconds)


async def set_step(user_id: int, step: str, ttl: int | None = None) -> None:
    """Save current conversation step. Empty string clears it."""
    if step:
        await set_data(user_id, _STEP_FIELD, step, ttl=ttl)
        _set_step_local(user_id, step)
        logger.info("%s step save user_id=%s step=%s", LogTag.REDIS, user_id, step)
    else:
        await clear_step(user_id)


async def get_step(user_id: int) -> str | None:
    """Read current conversation step from Redis."""
    hit, cached = _get_step_local(user_id)
    if hit:
        return cached
    value = await get_data(user_id, _STEP_FIELD)
    if value is None or value == "":
        _set_step_local(user_id, None)
        return None
    step = str(value)
    _set_step_local(user_id, step)
    return step


async def clear_step(user_id: int) -> None:
    """Remove only the step field."""
    previous = await get_step(user_id)
    await delete_data(user_id, _STEP_FIELD)
    _invalidate_step_local(user_id)
    if previous:
        logger.info("%s step clear user_id=%s was=%s", LogTag.REDIS, user_id, previous)


async def set_data(user_id: int, key: str, value: Any, ttl: int | None = None) -> None:
    """Save one temporary field for a user (e.g. amount, panel_name)."""
    await set_data_many(user_id, {key: value}, ttl=ttl)


async def set_data_many(user_id: int, values: dict[str, Any], ttl: int | None = None) -> None:
    """Save multiple temporary fields in one Redis round-trip."""
    if not values:
        return
    redis = await get_redis()
    if redis is None:
        return
    hash_key = build_state_key(user_id)
    try:
        mapping = {key: _serialize(value) for key, value in values.items()}
        await redis.hset(hash_key, mapping=mapping)
        await _refresh_ttl(redis, hash_key, ttl)
    except Exception as exc:
        logger.warning("Redis set_data_many(%s, %s): %s", user_id, list(values), exc)


async def get_data(user_id: int, key: str) -> Any:
    """Read one temporary field. Returns None if missing."""
    values = await get_data_many(user_id, (key,))
    return values.get(key)


async def get_data_many(user_id: int, keys: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Read multiple temporary fields in one Redis round-trip."""
    if not keys:
        return {}
    redis = await get_redis()
    if redis is None:
        return dict.fromkeys(keys)
    try:
        raw_values = await redis.hmget(build_state_key(user_id), list(keys))
        result: dict[str, Any] = {}
        for key, raw in zip(keys, raw_values, strict=False):
            result[key] = None if raw is None else _deserialize(raw)
        return result
    except Exception as exc:
        logger.warning("Redis get_data_many(%s, %s): %s", user_id, list(keys), exc)
        return dict.fromkeys(keys)


async def delete_data(user_id: int, key: str) -> None:
    """Remove one temporary field."""
    await delete_data_many(user_id, (key,))


async def delete_data_many(user_id: int, keys: tuple[str, ...] | list[str]) -> None:
    """Remove multiple temporary fields in one Redis round-trip."""
    if not keys:
        return
    redis = await get_redis()
    if redis is None:
        return
    try:
        await redis.hdel(build_state_key(user_id), *keys)
    except Exception as exc:
        logger.warning("Redis delete_data_many(%s, %s): %s", user_id, list(keys), exc)


async def clear_user(user_id: int) -> None:
    """Remove all Redis state for this user (step + all data)."""
    previous_step = await get_step(user_id)
    redis = await get_redis()
    if redis is None:
        _invalidate_step_local(user_id)
        return
    try:
        await redis.delete(build_state_key(user_id))
        _invalidate_step_local(user_id)
        if previous_step:
            logger.info("%s step clear (full) user_id=%s was=%s", LogTag.REDIS, user_id, previous_step)
    except Exception as exc:
        logger.warning("Redis clear_user(%s): %s", user_id, exc)


# --- optional app cache (used by admin stats, not user flow) ---


async def get_app_cache(key: str) -> str | None:
    redis = await get_redis()
    if redis is None:
        return None
    try:
        return await redis.get(build_cache_key(key))
    except Exception as exc:
        logger.warning("Redis get_app_cache(%s): %s", key, exc)
        return None


async def set_app_cache(key: str, value: str, ttl_seconds: int = 0) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        cache_key = build_cache_key(key)
        if ttl_seconds > 0:
            await redis.set(cache_key, value, ex=ttl_seconds)
        else:
            await redis.set(cache_key, value)
    except Exception as exc:
        logger.warning("Redis set_app_cache(%s): %s", key, exc)


async def delete_app_cache(key: str) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        await redis.delete(build_cache_key(key))
    except Exception as exc:
        logger.warning("Redis delete_app_cache(%s): %s", key, exc)


# --- old names (keep existing imports working) ---

set_current_step = set_step
get_current_step = get_step
clear_current_step = clear_step
set_user_state = set_data


async def get_user_state(user_id: int, key: str | None = None) -> Any:
    if key is None:
        redis = await get_redis()
        if redis is None:
            return {}
        try:
            raw = await redis.hgetall(build_state_key(user_id))
            return {field: _deserialize(value) for field, value in raw.items()} if raw else {}
        except Exception as exc:
            logger.warning("Redis get_user_state(%s): %s", user_id, exc)
            return {}
    return await get_data(user_id, key)


async def delete_user_state(user_id: int, key: str) -> None:
    await delete_data(user_id, key)


async def get_all_user_state(user_id: int) -> dict[str, Any]:
    return await get_user_state(user_id)


clear_user_conversation = clear_user

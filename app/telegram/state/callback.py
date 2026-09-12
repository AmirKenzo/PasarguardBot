"""Temporary callback payload storage in Redis."""

from __future__ import annotations

import json
from typing import Any

from app.db.redis import get_redis
from app.logger import get_logger
from app.telegram.state.keys import build_callback_key
from config import CALLBACK_TTL_SECONDS

logger = get_logger(__name__)


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_payload(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw


async def set_callback_payload(token: str, payload: Any, ttl: int | None = None) -> None:
    redis = await get_redis()
    if redis is None:
        return
    seconds = ttl if ttl is not None else CALLBACK_TTL_SECONDS
    key = build_callback_key(token)
    try:
        await redis.set(key, _serialize_payload(payload), ex=seconds)
    except Exception as exc:
        logger.warning("Redis set_callback_payload(%s): %s", token, exc)


async def get_callback_payload(token: str) -> Any:
    redis = await get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(build_callback_key(token))
        if raw is None:
            return None
        return _deserialize_payload(raw)
    except Exception as exc:
        logger.warning("Redis get_callback_payload(%s): %s", token, exc)
        return None


async def delete_callback_payload(token: str) -> None:
    redis = await get_redis()
    if redis is None:
        return
    try:
        await redis.delete(build_callback_key(token))
    except Exception as exc:
        logger.warning("Redis delete_callback_payload(%s): %s", token, exc)

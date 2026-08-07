"""Low-level Redis connection management."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.logger import get_logger
from config import (
    REDIS_HEALTH_CHECK_INTERVAL,
    REDIS_RETRY_INTERVAL_SECONDS,
    REDIS_SOCKET_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
    REDIS_URL,
)

logger = get_logger(__name__)

redis_client: Any | None = None
_init_lock = asyncio.Lock()
_last_failure_ts: float = 0.0


async def get_redis():
    """Return the shared async Redis client, or None if unavailable."""
    global redis_client, _last_failure_ts
    if redis_client is not None:
        return redis_client
    retry_after = float(REDIS_RETRY_INTERVAL_SECONDS or 10.0)
    if _last_failure_ts and (time.monotonic() - _last_failure_ts) < retry_after:
        return None
    async with _init_lock:
        if redis_client is not None:
            return redis_client
        if _last_failure_ts and (time.monotonic() - _last_failure_ts) < retry_after:
            return None
        try:
            from redis.asyncio import Redis

            connect_timeout = float(REDIS_SOCKET_CONNECT_TIMEOUT or 2.0)
            kwargs: dict[str, Any] = {
                "decode_responses": True,
                "socket_connect_timeout": connect_timeout,
                "health_check_interval": int(REDIS_HEALTH_CHECK_INTERVAL or 30),
            }
            # socket_timeout must stay unset (or > BRPOP wait) — a short read timeout
            # aborts send_queue's blocking brpop every poll and floods WARNING logs.
            socket_timeout = float(REDIS_SOCKET_TIMEOUT or 0.0)
            if socket_timeout > 0:
                kwargs["socket_timeout"] = socket_timeout

            client = Redis.from_url(REDIS_URL, **kwargs)
            await client.ping()
            redis_client = client
            _last_failure_ts = 0.0
            return redis_client
        except Exception as exc:
            _last_failure_ts = time.monotonic()
            logger.warning("Redis unavailable: %s", exc)
            return None


async def close_redis() -> None:
    """Close the shared Redis client."""
    global redis_client, _last_failure_ts
    if redis_client is None:
        return
    try:
        await redis_client.aclose()
    except Exception as exc:
        logger.warning("Redis close error: %s", exc)
    finally:
        redis_client = None
        _last_failure_ts = 0.0


class RedisManager:
    """Thin wrapper around module-level Redis helpers."""

    @staticmethod
    async def get_client():
        return await get_redis()

    @staticmethod
    async def close() -> None:
        await close_redis()

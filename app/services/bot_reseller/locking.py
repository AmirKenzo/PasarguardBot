from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

from app.db.redis import get_redis
from app.logger import get_logger
from app.telegram.state.keys import build_lock_key

log = get_logger(__name__)
_RENEW = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class MutationBusy(Exception):
    pass


class MutationLockUnavailable(Exception):
    pass


@dataclass
class ResellerMutationLease:
    redis: object
    key: str
    token: str
    lost: bool = False

    async def ensure_owned(self) -> None:
        if self.lost:
            raise MutationLockUnavailable
        try:
            async with asyncio.timeout(10):
                owned = await self.redis.eval(_RENEW, 1, self.key, self.token, 120)
        except Exception as exc:
            self.lost = True
            raise MutationLockUnavailable from exc
        if not owned:
            self.lost = True
            raise MutationLockUnavailable


@asynccontextmanager
async def reseller_mutation_lock(telegram_id: int):
    token = secrets.token_urlsafe(32)
    key = build_lock_key(telegram_id, "bot_reseller")
    try:
        async with asyncio.timeout(10):
            redis = await get_redis()
            if redis is None:
                raise MutationLockUnavailable
            acquired = await redis.set(key, token, nx=True, ex=120)
    except Exception as exc:
        raise MutationLockUnavailable from exc
    if not acquired:
        raise MutationBusy

    lease = ResellerMutationLease(redis, key, token)
    owner = asyncio.current_task()
    initial_cancellations = owner.cancelling()
    cancelled_by_lease = False

    async def renew():
        nonlocal cancelled_by_lease
        while True:
            await asyncio.sleep(30)
            try:
                await lease.ensure_owned()
            except MutationLockUnavailable:
                cancelled_by_lease = True
                owner.cancel()
                return

    renewal = asyncio.create_task(renew())
    try:
        await lease.ensure_owned()
        yield lease
        await lease.ensure_owned()
    except asyncio.CancelledError:
        if cancelled_by_lease:
            cancelled_by_lease = False
            if owner.uncancel() <= initial_cancellations:
                raise MutationLockUnavailable from None
        raise
    finally:
        if cancelled_by_lease:
            owner.uncancel()
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal
        try:
            async with asyncio.timeout(10):
                await redis.eval(_RELEASE, 1, key, token)
        except Exception:
            log.warning("Bot reseller mutation lease release failed reseller=%s", telegram_id)

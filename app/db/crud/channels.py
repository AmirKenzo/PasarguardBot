from __future__ import annotations

import time

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.channels import Channel
from app.logger import get_logger

log = get_logger(__name__)

_CHANNEL_LIST_TTL_SEC = 60.0
_channel_list_cache: tuple[float, list[dict]] | None = None


def invalidate_channel_list_cache() -> None:
    global _channel_list_cache
    _channel_list_cache = None


async def _notify_channel_gate_invalidation() -> None:
    """Bump membership-cache generation so all users re-check after lock-list changes."""
    try:
        from app.telegram.shared.guards.channel_gate import bump_channel_gate_generation

        await bump_channel_gate_generation()
    except Exception as exc:
        log.debug("channel gate generation bump skipped: %s", exc)


class ChannelManager:
    async def add_or_update_channel(self, channel_id, link, title):
        async with Session() as session:
            try:
                result = await session.execute(select(Channel).filter_by(id=channel_id))
                channel = result.scalars().first()

                if channel:
                    channel.link = link
                    channel.title = title
                    log.debug("Channel updated channel_id=%s", channel_id)
                else:
                    new_channel = Channel(id=channel_id, link=link, title=title)
                    session.add(new_channel)
                    log.debug("Channel added channel_id=%s", channel_id)

                await session.commit()
                invalidate_channel_list_cache()
                await _notify_channel_gate_invalidation()
                log.debug("Channel saved channel_id=%s", channel_id)

            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Channel DB commit failed channel_id=%s", channel_id, exc_info=e)

    async def delete_channel(self, channel_id):
        async with Session() as session:
            try:
                result = await session.execute(select(Channel).filter_by(id=channel_id))
                channel = result.scalars().first()

                if channel:
                    await session.delete(channel)
                    await session.commit()
                    invalidate_channel_list_cache()
                    await _notify_channel_gate_invalidation()
                    log.debug("Channel deleted channel_id=%s", channel_id)
                else:
                    log.debug("Channel not found for delete channel_id=%s", channel_id)

            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Channel DB commit failed channel_id=%s", channel_id, exc_info=e)

    async def get_channel(self, channel_id):
        async with Session() as session:
            result = await session.execute(select(Channel).filter_by(id=channel_id))
            channel = result.scalars().first()
            if channel:
                return {"id": channel.id, "link": channel.link, "title": channel.title}
            log.debug("Channel not found channel_id=%s", channel_id)
            return None

    async def get_all_channels(self):
        global _channel_list_cache
        now = time.monotonic()
        if _channel_list_cache is not None:
            ts, rows = _channel_list_cache
            if now - ts <= _CHANNEL_LIST_TTL_SEC:
                return [dict(row) for row in rows]

        async with Session() as session:
            result = await session.execute(select(Channel))
            channels = result.scalars().all()
            rows = [{"id": ch.id, "link": ch.link, "title": ch.title} for ch in channels]
            _channel_list_cache = (now, rows)
            return [dict(row) for row in rows]

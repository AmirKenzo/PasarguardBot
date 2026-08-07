import time

from sqlalchemy import delete, select

from app.db.base import get_db
from app.db.models.log_channels import LogChannel

_DEST_CACHE_TTL_SEC = 60.0
_dest_cache: dict[str, tuple[float, dict | None]] = {}


def invalidate_log_channel_dest_cache(log_type: str | None = None) -> None:
    if log_type is None:
        _dest_cache.clear()
    else:
        _dest_cache.pop(str(log_type), None)


class LogChannelManager:
    def __init__(self):
        pass

    async def create_or_update_log_channel(
        self,
        log_type: str,
        destination_type: str,
        chat_id: int,
        topic_id: int | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> LogChannel:
        """Create or update log channel configuration"""
        async for db in get_db():
            # Check if log channel already exists in current session
            stmt = select(LogChannel).where(LogChannel.log_type == log_type, LogChannel.is_active)
            result = await db.execute(stmt)
            existing_channel = result.scalar_one_or_none()

            if existing_channel:
                # Update existing channel
                existing_channel.destination_type = destination_type
                existing_channel.chat_id = chat_id
                existing_channel.topic_id = topic_id
                existing_channel.description = description
                existing_channel.is_active = is_active

                await db.commit()
                db.expunge(existing_channel)
                invalidate_log_channel_dest_cache(log_type)
                return existing_channel
            # Create new channel
            log_channel = LogChannel(
                log_type=log_type,
                destination_type=destination_type,
                chat_id=chat_id,
                topic_id=topic_id,
                description=description,
                is_active=is_active,
            )

            db.add(log_channel)
            await db.commit()
            db.expunge(log_channel)
            invalidate_log_channel_dest_cache(log_type)
            return log_channel
        return None

    async def get_log_channel_by_type(self, log_type: str) -> LogChannel | None:
        """Get active log channel configuration by type"""
        async for db in get_db():
            stmt = select(LogChannel).where(LogChannel.log_type == log_type, LogChannel.is_active)
            result = await db.execute(stmt)
            log_channel = result.scalar_one_or_none()
            if log_channel:
                db.expunge(log_channel)
            return log_channel
        return None

    async def get_all_log_channels(self) -> list[LogChannel]:
        """Get all log channel configurations"""
        async for db in get_db():
            stmt = select(LogChannel).order_by(LogChannel.log_type)
            result = await db.execute(stmt)
            log_channels = list(result.scalars().all())
            for log_channel in log_channels:
                db.expunge(log_channel)
            return log_channels
        return None

    async def get_log_channels_by_type(self, log_type: str) -> list[LogChannel]:
        """Get all log channel configurations for a specific type"""
        async for db in get_db():
            stmt = select(LogChannel).where(LogChannel.log_type == log_type)
            result = await db.execute(stmt)
            log_channels = list(result.scalars().all())
            for log_channel in log_channels:
                db.expunge(log_channel)
            return log_channels
        return None

    async def update_log_channel(
        self,
        log_channel_id: int,
        destination_type: str | None = None,
        chat_id: int | None = None,
        topic_id: int | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> LogChannel | None:
        """Update an existing log channel configuration"""
        async for db in get_db():
            log_channel = await db.get(LogChannel, log_channel_id)
            if not log_channel:
                return None

            if destination_type is not None:
                log_channel.destination_type = destination_type
            if chat_id is not None:
                log_channel.chat_id = chat_id
            if topic_id is not None:
                log_channel.topic_id = topic_id
            if description is not None:
                log_channel.description = description
            if is_active is not None:
                log_channel.is_active = is_active

            await db.commit()
            db.expunge(log_channel)
            invalidate_log_channel_dest_cache(log_channel.log_type)
            return log_channel
        return None

    async def deactivate_log_channel(self, log_channel_id: int) -> bool:
        """Deactivate a specific log channel"""
        async for db in get_db():
            log_channel = await db.get(LogChannel, log_channel_id)
            if not log_channel:
                return False

            log_type = log_channel.log_type
            log_channel.is_active = False
            await db.commit()
            invalidate_log_channel_dest_cache(log_type)
            return True
        return None

    async def deactivate_log_channels_by_type(self, log_type: str) -> int:
        """Deactivate all log channels of a specific type"""
        async for db in get_db():
            stmt = select(LogChannel).where(LogChannel.log_type == log_type, LogChannel.is_active)
            result = await db.execute(stmt)
            log_channels = result.scalars().all()

            for log_channel in log_channels:
                log_channel.is_active = False

            await db.commit()
            invalidate_log_channel_dest_cache(log_type)
            return len(log_channels)
        return None

    async def delete_log_channel(self, log_channel_id: int) -> bool:
        """Delete a log channel configuration"""
        async for db in get_db():
            log_channel = await db.get(LogChannel, log_channel_id)
            if not log_channel:
                return False

            log_type = log_channel.log_type
            await db.delete(log_channel)
            await db.commit()
            invalidate_log_channel_dest_cache(log_type)
            return True
        return None

    async def delete_log_channels_by_type(self, log_type: str) -> int:
        """Delete all log channel configurations of a specific type"""
        async for db in get_db():
            stmt = delete(LogChannel).where(LogChannel.log_type == log_type)
            result = await db.execute(stmt)
            await db.commit()
            invalidate_log_channel_dest_cache(log_type)
            return result.rowcount
        return None

    async def get_log_channel_destination(self, log_type: str) -> dict | None:
        """Get the destination information for a log type (for sending messages)"""
        key = str(log_type)
        now = time.monotonic()
        cached = _dest_cache.get(key)
        if cached is not None:
            ts, dest = cached
            if now - ts <= _DEST_CACHE_TTL_SEC:
                return dest

        async for db in get_db():
            stmt = select(LogChannel.chat_id, LogChannel.topic_id).where(
                LogChannel.log_type == log_type, LogChannel.is_active
            )
            result = await db.execute(stmt)
            row = result.first()
            dest = None if not row else {"chat_id": row.chat_id, "topic_id": row.topic_id}
            _dest_cache[key] = (now, dest)
            return dest
        return None

"""Telethon client lifecycle and API event logging."""

from __future__ import annotations

import asyncio

from telethon import TelegramClient

from app.logger.setup import get_logger

logger = get_logger("telegram")

_watch_tasks: dict[int, asyncio.Task[None]] = {}


def register_telethon_client(client: TelegramClient) -> None:
    """Watch for unexpected disconnects while the client is running."""
    key = id(client)
    existing = _watch_tasks.get(key)
    if existing is not None and not existing.done():
        return
    _watch_tasks[key] = asyncio.create_task(_watch_disconnect(client))


def unregister_telethon_client(client: TelegramClient) -> None:
    """Stop the disconnect watcher (call before ``disconnect()`` to avoid log spam)."""
    task = _watch_tasks.pop(id(client), None)
    if task is not None and not task.done():
        task.cancel()


async def _watch_disconnect(client: TelegramClient) -> None:
    try:
        while client.is_connected():
            await client.disconnected
            if not client.is_connected():
                break
            logger.warning("Telegram connection lost — awaiting reconnect")
    except asyncio.CancelledError:
        pass

"""Registration API handed to every bot module's ``setup``."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from telethon import TelegramClient
from telethon.events.common import EventBuilder

from app.jobs.scheduler import scheduler
from app.logger import get_logger

type EventCallback = Callable[[Any], Coroutine[Any, Any, Any]]


class PluginContext:
    """What a module registers its handlers and jobs through.

    Attributes it does not define resolve on the Telegram client, so existing
    ``setup(client)`` functions accept a context unchanged.
    """

    def __init__(self, name: str, client: TelegramClient) -> None:
        self.name = name
        self.client = client
        self.logger = get_logger(f"module.{name}")
        self.handler_count = 0
        self.job_ids: list[str] = []

    def __getattr__(self, item: str) -> Any:
        if item == "client":
            raise AttributeError(item)
        return getattr(self.client, item)

    def add_event_handler(self, callback: EventCallback, event: EventBuilder) -> EventCallback:
        self.client.add_event_handler(callback, event)
        self.handler_count += 1
        return callback

    def on(self, event: EventBuilder) -> Callable[[EventCallback], EventCallback]:
        def decorator(callback: EventCallback) -> EventCallback:
            return self.add_event_handler(callback, event)

        return decorator

    def add_job(self, func: Callable[..., Any], trigger: str, *, job_id: str, **trigger_args: Any) -> str:
        """Schedule an APScheduler job under ``<module name>.<job_id>``."""
        full_id = f"{self.name}.{job_id}"
        scheduler.add_job(func, trigger, id=full_id, replace_existing=True, **trigger_args)
        self.job_ids.append(full_id)
        return full_id

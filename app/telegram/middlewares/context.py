"""Shared context passed through the middleware pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from telethon import events

from config import ADMIN_ID

EventKind = Literal["newmessage", "callback", "other"]


@dataclass
class MiddlewareContext:
    """Per-update state for middleware chains."""

    event: events.common.EventCommon
    kind: EventKind
    user_id: int | None
    is_admin: bool = False
    is_private: bool = False
    is_channel: bool = False
    is_group: bool = False
    event_id: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_event(cls, event: events.common.EventCommon) -> MiddlewareContext:
        user_id = getattr(event, "sender_id", None)
        is_channel = bool(getattr(event, "is_channel", False))
        is_group = bool(getattr(event, "is_group", False))
        is_private = bool(getattr(event, "is_private", False))

        if isinstance(event, events.CallbackQuery.Event):
            kind: EventKind = "callback"
            event_id = getattr(event, "msg_id", None) or getattr(event, "id", None)
        elif isinstance(event, events.NewMessage.Event):
            kind = "newmessage"
            if hasattr(event, "message") and event.message:
                event_id = getattr(event.message, "id", None)
            else:
                event_id = getattr(event, "id", None)
        else:
            kind = "other"
            event_id = getattr(event, "id", None)

        is_admin = bool(user_id and user_id in ADMIN_ID)

        return cls(
            event=event,
            kind=kind,
            user_id=user_id,
            is_admin=is_admin,
            is_private=is_private,
            is_channel=is_channel,
            is_group=is_group,
            event_id=event_id,
        )

    @property
    def is_callback(self) -> bool:
        return self.kind == "callback"

    @property
    def is_newmessage(self) -> bool:
        return self.kind == "newmessage"

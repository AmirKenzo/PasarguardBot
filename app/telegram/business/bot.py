"""Telegram Business message API — send/edit/reply via business connection."""

from __future__ import annotations

import random

from telethon.errors import FloodWaitError
from telethon.tl import functions, types
from telethon.utils import sanitize_parse_mode

from app import Kenzo
from app.logger import get_logger
from app.telegram.shared.utils.api import sleep_flood_wait

logger = get_logger(__name__)


def _extract_reply_message_id(updates) -> int | None:
    if updates is None:
        return None
    for update in getattr(updates, "updates", []):
        msg = getattr(update, "message", None)
        if msg is not None and getattr(msg, "id", None):
            return msg.id
    return None


def _random_id() -> int:
    return random.randint(-(2**63), 2**63 - 1)


async def invoke_business(connection_id: str, query: types.TLRequest, *, max_flood_retries: int = 1):
    """Run a TL request inside a business connection (with short FloodWait retry)."""
    for attempt in range(max_flood_retries + 1):
        try:
            return await Kenzo(functions.InvokeWithBusinessConnectionRequest(connection_id=connection_id, query=query))
        except FloodWaitError as e:
            logger.warning("FloodWait %ss in business_api", e.seconds)
            if attempt >= max_flood_retries or e.seconds > 20:
                raise
            await sleep_flood_wait(e)
    raise RuntimeError("invoke_business exhausted flood retries")


class BusinessMessage:
    """Helper for Telegram Business DMs (text send/edit/reply)."""

    def __init__(self, event: types.UpdateBotNewBusinessMessage):
        self.event = event
        self.connection_id = event.connection_id
        self.peer_id = event.message.peer_id
        self.chat_id = event.message.chat_id
        self.message_id = event.message.id

    async def _get_chat_entity(self):
        return await Kenzo.get_input_entity(self.chat_id)

    def _parse_text(self, text: str, parse_mode: str | None) -> tuple[str, list]:
        if not parse_mode:
            return text, []
        if parse_mode == "md" and hasattr(Kenzo, "parse_mode") and Kenzo.parse_mode:
            return Kenzo.parse_mode.parse(text)
        return sanitize_parse_mode(parse_mode).parse(text)

    async def _invoke(self, query: types.TLRequest):
        return await invoke_business(self.connection_id, query)

    async def reply(self, text: str, parse_mode: str = "md") -> None:
        await self._send_reply(text, parse_mode=parse_mode)

    async def _send_reply(
        self,
        text: str,
        *,
        parse_mode: str | None = "md",
        buttons=None,
        reply_to_msg_id: int | None = None,
    ) -> int | None:
        entity = await self._get_chat_entity()
        message, entities = self._parse_text(text, parse_mode)

        reply_markup = None
        if buttons:
            reply_markup = Kenzo.build_reply_markup(buttons) if isinstance(buttons, list) else buttons

        target_id = self.message_id if reply_to_msg_id is None else reply_to_msg_id
        reply_to = types.InputReplyToMessage(reply_to_msg_id=target_id) if target_id else None

        request = functions.messages.SendMessageRequest(
            peer=entity,
            message=message,
            entities=entities,
            reply_to=reply_to,
            reply_markup=reply_markup,
            random_id=_random_id(),
        )
        updates = await self._invoke(request)
        return _extract_reply_message_id(updates)

    async def send_message(self, text: str, parse_mode: str = "md") -> None:
        entity = await self._get_chat_entity()
        message, entities = self._parse_text(text, parse_mode)
        request = functions.messages.SendMessageRequest(
            peer=entity,
            message=message,
            entities=entities,
            random_id=_random_id(),
        )
        await self._invoke(request)

    async def edit_message(self, text: str, parse_mode: str = "md", buttons=None) -> None:
        entity = await self._get_chat_entity()
        message, entities = self._parse_text(text, parse_mode)

        reply_markup = None
        if buttons:
            reply_markup = Kenzo.build_reply_markup(buttons) if isinstance(buttons, list) else buttons

        request = functions.messages.EditMessageRequest(
            peer=entity,
            id=self.message_id,
            message=message,
            entities=entities,
            reply_markup=reply_markup,
        )
        await self._invoke(request)

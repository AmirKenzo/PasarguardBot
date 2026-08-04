"""Raw message handlers for slim Telegram Business admin commands."""

from telethon import events
from telethon.tl import types

from app.logger import get_logger
from app.telegram.business.bot import BusinessMessage
from app.telegram.business.message import service
from app.telegram.business.shared.guards.access import (
    ensure_connection_allowed,
    get_sender_id,
    is_admin_business_sender,
)

logger = get_logger(__name__)


async def handle_business_message(event: types.UpdateBotNewBusinessMessage) -> None:
    try:
        await _handle_business_message(event)
    except Exception:
        logger.exception("Business message handler failed")


async def _handle_business_message(event: types.UpdateBotNewBusinessMessage) -> None:
    msg = event.message.message
    if not msg:
        return

    connection_id = event.connection_id
    sender_id = get_sender_id(event.message)
    if not await ensure_connection_allowed(connection_id, sender_id=sender_id):
        logger.info("Access denied for business message: connection_id=%s", connection_id)
        return

    bm = BusinessMessage(event)
    if is_admin_business_sender(event, sender_id):
        await service.handle_admin_commands(bm, event, msg.strip(), sender_id)


def register(client):
    client.add_event_handler(handle_business_message, events.Raw(types.UpdateBotNewBusinessMessage))

from __future__ import annotations

from typing import TYPE_CHECKING

from app import Kenzo
from app.logger import get_logger
from config import LOG_CHANNEL

if TYPE_CHECKING:
    from app.logger import LogType

logger = get_logger(__name__)


async def _send_to_entity(**kwargs):
    if "file" in kwargs:
        return await Kenzo.send_file(**kwargs)
    return await Kenzo.send_message(**kwargs)


async def send_log_message(log_type: str | LogType, **kwargs):
    """Send a log message/file to the configured log destination."""
    if hasattr(log_type, "value"):
        log_type = log_type.value

    try:
        # Local import: avoids a circular import with app.db.crud.log_channels.
        from app.db.crud.log_channels import LogChannelManager

        log_manager = LogChannelManager()
        destination = await log_manager.get_log_channel_destination(log_type)

        if destination:
            chat_id = destination["chat_id"]
            topic_id = destination.get("topic_id")
            kwargs["entity"] = int(chat_id)
            if topic_id and "reply_to" not in kwargs:
                kwargs["reply_to"] = int(topic_id)
        elif LOG_CHANNEL is not None:
            kwargs["entity"] = LOG_CHANNEL
        else:
            logger.debug("Log channel not configured; skipping %s", log_type)
            return None

        return await _send_to_entity(**kwargs)

    except Exception as e:
        logger.error("Error sending log message for %s: %s", log_type, e)
        if LOG_CHANNEL is None:
            return None
        try:
            kwargs["entity"] = LOG_CHANNEL
            return await _send_to_entity(**kwargs)
        except Exception as fallback_error:
            logger.error("Error in fallback log sending: %s", fallback_error)
            return None

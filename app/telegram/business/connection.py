from telethon import events
from telethon.tl import functions, types

from app import Kenzo
from app.logger import get_logger
from app.telegram.business.shared.guards.access import is_business_admin, register_connection
from config import ADMIN_ID

logger = get_logger(__name__)


@Kenzo.on(events.Raw(types.UpdateBotBusinessConnect))
async def handle_business_connect(event: types.UpdateBotBusinessConnect) -> None:
    connection_id = event.connection.connection_id
    user_id = event.connection.user_id
    logger.info("New business connection: connection_id=%s user_id=%s", connection_id, user_id)

    if not is_business_admin(user_id):
        logger.info(
            "Access denied for business connection: user_id=%s (allowed=%s)",
            user_id,
            ADMIN_ID,
        )
        try:
            await Kenzo(functions.bots.DisconnectBusinessConnectionRequest(connection_id=connection_id))
        except Exception as exc:
            logger.warning("Error terminating business connection %s: %s", connection_id, exc)
        return

    register_connection(connection_id, user_id)
    logger.info("Authorized business connection registered for user_id=%s", user_id)

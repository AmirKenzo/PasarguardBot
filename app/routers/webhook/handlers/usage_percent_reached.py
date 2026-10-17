"""
Handler for reached_usage_percent webhook event.
"""

from telethon import errors

from app import Kenzo
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import set_user_status
from app.logger import get_logger
from app.models.router_models import WebhookEvent
from app.routers.webhook.helpers import find_service_by_username
from app.services.panels.settings import panel_webhook_notifications_enabled
from app.utils.formatting.traffic import format_size
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

logger = get_logger(__name__)


async def handle_usage_percent_reached(event: WebhookEvent) -> None:
    """Handle usage percent reached event."""
    logger.info(f"📊 Usage percent reached: {event.username}, usage_percent: {event.used_percent}%")

    if not event.user:
        logger.warning(f"No user data in webhook event for {event.username}")
        return
    success, service, panel = await find_service_by_username(event.username)

    if not success or not service:
        logger.warning(f"Service not found for username: {event.username}")
        return

    if not panel or not panel_webhook_notifications_enabled(panel):
        logger.info(f"Webhook notifications disabled for panel {panel.code if panel else 'unknown'}, skipping")
        return

    used_percent = event.used_percent or 0
    used_traffic = event.user.used_traffic or 0
    data_limit = event.user.data_limit or 0
    remaining = data_limit - used_traffic

    remaining_text = format_size(remaining, decimal_places=2)
    message_template = await get_bot_text(
        key="webhook_notification_low_data",
        default=DEFAULT_BOT_TEXTS["webhook_notification_low_data"],
        lang="fa",
    )

    message = (
        message_template.replace("{remaining_volume}", remaining_text)
        .replace("{service_code}", str(service.code))
        .replace("{config_name}", service.username)
    )

    service_crud = ServiceCRUD()
    try:
        await Kenzo.send_message(service.id, message, parse_mode="html")
        logger.info(
            f"✅ Low data notification sent to user {service.id} for service {service.code} ({used_percent:.1f}% used)"
        )
        await service_crud.update_service(service.code, low_volume_notified=True)

    except errors.FloodWaitError as e:
        logger.warning(f"FloodWait error for user {service.id}: {e}")
        await service_crud.update_service(service.code, low_volume_notified=True)

    except errors.InputUserDeactivatedError:
        logger.warning(f"User {service.id} is deactivated")
        await set_user_status(service.id, "DeleteAccount")
        await service_crud.update_service(service.code, low_volume_notified=True)

    except errors.UserIsBlockedError:
        logger.warning(f"User {service.id} blocked the bot")
        await set_user_status(service.id, "BlockedBot")
        await service_crud.update_service(service.code, low_volume_notified=True)

    except Exception as e:
        logger.error(f"Failed to send low data notification to user {service.id}: {e}")

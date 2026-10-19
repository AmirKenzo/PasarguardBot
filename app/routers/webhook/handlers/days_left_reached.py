"""
Handler for reached_days_left webhook event.
"""

from datetime import datetime

from telethon import errors

from app import Kenzo
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import set_user_status
from app.logger import get_logger
from app.models.router_models import WebhookEvent
from app.routers.webhook.helpers import find_service_by_username
from app.services.panels.settings import panel_webhook_notifications_enabled
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

logger = get_logger(__name__)


async def handle_days_left_reached(event: WebhookEvent) -> None:
    """Handle days left reached event."""
    logger.info(f"⏳ Days left reached: {event.username}, days_left: {event.days_left}")

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

    time_diff_seconds = 0
    if event.user.expire:
        try:
            expire_str = event.user.expire
            if isinstance(expire_str, str):
                expire_dt = datetime.fromisoformat(expire_str.replace("Z", "+00:00"))
            else:
                expire_dt = datetime.fromtimestamp(expire_str)

            now_dt = datetime.now(expire_dt.tzinfo) if expire_dt.tzinfo else datetime.now()
            time_diff = expire_dt - now_dt
            time_diff_seconds = int(time_diff.total_seconds())

            if time_diff_seconds < 0:
                time_diff_seconds = 0
        except Exception as e:
            logger.warning(f"Failed to parse expire date: {e}, using days_left fallback")
            # Fallback to days_left if expire parsing fails
            days_left = event.days_left or 0
            time_diff_seconds = days_left * 24 * 3600
    else:
        # Fallback to days_left if no expire date
        days_left = event.days_left or 0
        time_diff_seconds = days_left * 24 * 3600

    days = time_diff_seconds // 86400
    hours = (time_diff_seconds % 86400) // 3600
    minutes = (time_diff_seconds % 3600) // 60

    time_parts = []
    if days > 0:
        time_parts.append(f"{days} روز")
    if hours > 0:
        time_parts.append(f"{hours} ساعت")
    if minutes > 0 or len(time_parts) == 0:
        time_parts.append(f"{minutes} دقیقه")

    time_text = " و ".join(time_parts)

    message_template = await get_bot_text(
        key="webhook_notification_expiration_warning",
        default=DEFAULT_BOT_TEXTS["webhook_notification_expiration_warning"],
        lang="fa",
    )

    message = (
        message_template.replace("{service_code}", str(service.code))
        .replace("{config_name}", service.username)
        .replace("{time_remaining}", time_text)
    )

    service_crud = ServiceCRUD()
    try:
        await Kenzo.send_message(service.id, message, parse_mode="html")
        logger.info(f"✅ Expiration notification sent to user {service.id} for service {service.code}")
        await service_crud.update_service(service.code, expire_notified=True)

    except errors.FloodWaitError as e:
        logger.warning(f"FloodWait error for user {service.id}: {e}")
        await service_crud.update_service(service.code, expire_notified=True)

    except errors.InputUserDeactivatedError:
        logger.warning(f"User {service.id} is deactivated")
        await set_user_status(service.id, "DeleteAccount")
        await service_crud.update_service(service.code, expire_notified=True)

    except errors.UserIsBlockedError:
        logger.warning(f"User {service.id} blocked the bot")
        await set_user_status(service.id, "BlockedBot")
        await service_crud.update_service(service.code, expire_notified=True)

    except Exception as e:
        logger.error(f"Failed to send expiration notification to user {service.id}: {e}")

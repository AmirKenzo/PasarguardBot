"""
Handler for user_limited webhook event - data usage reached limit.
"""

import asyncio

from pasarguard import PasarguardAPI
from telethon import errors

from app import Kenzo
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import set_user_status
from app.logger import LogType, get_logger
from app.models.router_models import WebhookEvent
from app.routers.webhook.helpers import find_service_by_username
from app.services.billing.renewal import require_panel_userid
from app.services.panels.settings import panel_webhook_notifications_enabled
from app.telegram.shared.utils.logging import send_log_message
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def handle_user_limited(event: WebhookEvent) -> None:
    """Handle user limited event - data usage reached limit."""
    logger.warning(f"⚠️ User limited (data exhausted): {event.username}")

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

    if getattr(service, "is_test", False) is True:
        if panel:
            try:
                api = PasarguardAPI(panel.base_url)
                await api.remove_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
            except Exception as e:
                logger.error(f"Failed to remove test service (volume exhausted) {service.username} from panel: {e}")
        await ServiceCRUD().delete_service(service.code)
        logger.info(f"Test service {service.username} (code {service.code}) removed immediately (volume exhausted)")
        try:
            await Kenzo.send_message(
                service.id,
                f"کانفیگ تست شما با نام **{service.username}** به دلیل اتمام حجم پاک شد.",
            )
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except errors.InputUserDeactivatedError:
            await set_user_status(service.id, "DeleteAccount")
        except errors.UserIsBlockedError:
            await set_user_status(service.id, "BlockedBot")
        except Exception as e:
            logger.error(f"Test service delete notify failed for {service.id}: {e}")
        log_msg = (
            f"🧪 <b>کانفیگ تست پاک شد</b> (وب‌هوک: اتمام حجم)\n\n"
            f"◾️ کد سرویس: <code>{service.code}</code>\n"
            f"◾️ اسم کانفیگ: <code>{service.username}</code>\n"
            f"◾️ شناسه کاربر: <code>{service.id}</code>\n"
            f"◾️ پنل: {panel.name if panel else '—'}"
        )
        await send_log_message(LogType.OTHER, message=log_msg, parse_mode="html")
        return

    if event.user.data_limit and event.user.used_traffic >= event.user.data_limit:
        logger.warning(f"🚨 DATA EXHAUSTED - User {event.username} has used all their data!")

        message_template = await get_bot_text(
            key="webhook_notification_data_exhausted",
            default=(
                "<b>#اطلاع_رسانی</b>\n\n"
                "<b>#⃣ کد سرویس(در ربات): {service_code}</b>\n"
                "<b>🔷 اسم کانفیگ: {config_name}</b>\n"
                "<b>📅 سرویس شما به دلیل اتمام حجم غیرفعال شده است.</b>\n"
                "<b>👈🏻 شما می‌توانید سرویس خود را در بخش (سرویس های من) تمدید کنید.</b>\n\n"
                "<b>#notification_{service_code}</b>"
            ),
            lang="fa",
        )
        message = message_template.replace("{service_code}", str(service.code)).replace(
            "{config_name}", service.username
        )
        service_crud = ServiceCRUD()
        try:
            await Kenzo.send_message(service.id, message, parse_mode="html")
            logger.info(f"✅ Data exhaustion notification sent to user {service.id} for service {service.code}")

        except errors.FloodWaitError as e:
            logger.warning(f"FloodWait error for user {service.id}: {e}")

        except errors.InputUserDeactivatedError:
            logger.warning(f"User {service.id} is deactivated")
            await set_user_status(service.id, "DeleteAccount")

        except errors.UserIsBlockedError:
            logger.warning(f"User {service.id} blocked the bot")
            await set_user_status(service.id, "BlockedBot")

        except Exception as e:
            logger.error(f"Failed to send data exhaustion notification to user {service.id}: {e}")
        finally:
            # Prevent cron check_low_volume from re-sending every minute
            await service_crud.update_service(service.code, low_volume_notified=True)

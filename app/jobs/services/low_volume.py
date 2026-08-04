import asyncio
import time
from datetime import datetime

from pasarguard import PasarguardAPI
from telethon import errors

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import set_user_status
from app.logger import LogTag, LogType, get_logger
from app.services.billing.renewal import require_panel_userid
from app.services.panels.settings import panel_webhook_notifications_enabled
from app.telegram.shared.utils.logging import send_log_message
from app.utils.formatting.traffic import format_size
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


async def check_low_volume():
    """Notify users when their remaining traffic is below 1GB."""
    start_time = time.time()
    logger.debug("%s check_low_volume started", LogTag.JOB)
    # Check if there are any panels WITHOUT webhooks
    all_panels = await PanelsManager().get_all_panels()
    panels_without_webhook = [p for p in all_panels if not panel_webhook_notifications_enabled(p)]

    if not panels_without_webhook:
        logger.debug("%s check_low_volume: All panels have webhooks enabled, skipping cron job", LogTag.JOB)
        return

    panel_codes_without_webhook = [p.code for p in panels_without_webhook]
    logger.debug(f"{LogTag.JOB} check_low_volume: {len(panels_without_webhook)} panels without webhooks")

    service_crud = ServiceCRUD()

    # Process in batches of 500
    batch_size = 500
    offset = 0
    total_fetched = 0
    panel_map: dict[int, dict[str, list]] = {}

    while True:
        # Fetch batch
        batch = await service_crud.get_all_services_by_panels_batch(panel_codes_without_webhook, batch_size, offset)

        if not batch:
            break

        logger.debug(f"{LogTag.JOB} check_low_volume: Fetched batch {offset}-{offset + len(batch)}")
        total_fetched += len(batch)

        # Group services by panel code and username
        for service in batch:
            if service.in_panel:
                panel_map.setdefault(service.in_panel, {}).setdefault(service.username, []).append(service)

        offset += batch_size

    if not panel_map:
        logger.debug("%s check_low_volume: No services found on panels without webhooks, skipping", LogTag.JOB)
        return

    logger.debug(f"{LogTag.JOB} check_low_volume: Total {total_fetched} services grouped into {len(panel_map)} panels")

    api_calls = 0
    notifications_sent = 0
    test_services_deleted = 0
    current_time = int(datetime.now().timestamp())

    for panel_code, users in panel_map.items():
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            logger.warning(f"{LogTag.JOB} check_low_volume: Panel {panel_code} not found, skipping")
            continue

        logger.debug(f"{LogTag.JOB} check_low_volume: Checking panel {panel.name} with {len(users)} users")
        api = PasarguardAPI(panel.base_url)
        offset = 0
        page_size = 200

        while True:
            try:
                api_calls += 1
                resp = await api.get_users(
                    token=panel.cookie,
                    limit=page_size,
                    offset=offset,
                )
            except Exception as e:
                logger.error(f"{LogTag.JOB} check_low_volume: API error for panel {panel.name}: {e}")
                break

            if not resp.users:
                break

            for user in resp.users:
                if user.username not in users:
                    continue

                remaining = user.data_limit - (user.used_traffic or 0)
                for service in users[user.username]:
                    is_test = getattr(service, "is_test", False) is True
                    if is_test:
                        volume_exhausted = remaining <= 0
                        time_expired = service.expiration_time is not None and service.expiration_time <= current_time
                        if volume_exhausted or time_expired:
                            try:
                                if service.panel_userid:
                                    await api.remove_user_by_id(
                                        user_id=require_panel_userid(service), token=panel.cookie
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"{LogTag.JOB} check_low_volume: remove test user {service.username} from panel: {e}"
                                )
                            ok, _ = await service_crud.delete_service(service.code)
                            if ok:
                                test_services_deleted += 1
                                logger.info(
                                    f"{LogTag.JOB} check_low_volume: deleted test service {service.code} "
                                    f"(volume_exhausted={volume_exhausted}, time_expired={time_expired})"
                                )
                                reason = "اتمام حجم" if volume_exhausted else "اتمام زمان"
                                notify_text = f"کانفیگ تست شما با نام **{service.username}** به دلیل {reason} پاک شد."
                                try:
                                    await Kenzo.send_message(service.id, notify_text)
                                except errors.FloodWaitError as e:
                                    await asyncio.sleep(e.seconds)
                                except errors.InputUserDeactivatedError:
                                    await set_user_status(service.id, "DeleteAccount")
                                except errors.UserIsBlockedError:
                                    await set_user_status(service.id, "BlockedBot")
                                except Exception as e:
                                    logger.error(f"test service delete notify failed for {service.id}: {e}")
                                log_msg = (
                                    f"🧪 <b>کانفیگ تست پاک شد</b> (به دلیل {reason})\n\n"
                                    f"◾️ کد سرویس: <code>{service.code}</code>\n"
                                    f"◾️ اسم کانفیگ: <code>{service.username}</code>\n"
                                    f"◾️ شناسه کاربر: <code>{service.id}</code>\n"
                                    f"◾️ پنل: {panel.name if panel else '—'}"
                                )
                                await send_log_message(LogType.OTHER, message=log_msg, parse_mode="html")
                        continue

                    if remaining <= 0:
                        if not service.low_volume_notified:
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
                            try:
                                await Kenzo.send_message(service.id, message, parse_mode="html")
                                notifications_sent += 1
                            except errors.FloodWaitError as e:
                                await asyncio.sleep(e.seconds)
                            except errors.InputUserDeactivatedError:
                                await set_user_status(service.id, "DeleteAccount")
                            except errors.UserIsBlockedError:
                                await set_user_status(service.id, "BlockedBot")
                            except Exception as e:
                                logger.error(f"data exhausted notify failed for {service.id}: {e}")
                            finally:
                                await service_crud.update_service(service.code, low_volume_notified=True)
                                service.low_volume_notified = True
                        continue

                    if remaining <= 1 * 1024**3:
                        if not service.low_volume_notified:
                            try:
                                await Kenzo.send_message(
                                    service.id,
                                    (
                                        "**#Low_Data**\n"
                                        "🔔 حجم باقی‌مانده‌ی سرویس شما: "
                                        f"**{format_size(remaining, decimal_places=2)}**\n"
                                        "برای جلوگیری از قطع سرویس، لطفاً پلن خود را تمدید یا ارتقا دهید.\n\n"
                                        f"🔢 **کدسرویس**: `{service.code}`\n"
                                        f"👤 **اسم کانفیگ**: `{service.username}`"
                                    ),
                                )
                                notifications_sent += 1
                            except errors.FloodWaitError as e:
                                await asyncio.sleep(e.seconds)
                            except errors.InputUserDeactivatedError:
                                await set_user_status(service.id, "DeleteAccount")
                            except errors.UserIsBlockedError:
                                await set_user_status(service.id, "BlockedBot")
                            except Exception as e:
                                logger.error(f"low volume warn failed for {service.id}: {e}")
                            finally:
                                await service_crud.update_service(service.code, low_volume_notified=True)
                    elif service.low_volume_notified:
                        await service_crud.update_service(service.code, low_volume_notified=False)

            offset += page_size

    elapsed = time.time() - start_time
    logger.info(
        f"{LogTag.JOB} check_low_volume | duration={elapsed:.2f}s, "
        f"api={api_calls}, notify={notifications_sent}, test_deleted={test_services_deleted}"
    )

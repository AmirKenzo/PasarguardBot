import time
from types import SimpleNamespace

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

_LOW_VOLUME_BYTES = 1 * 1024**3
_BATCH_SIZE = 500
_PAGE_SIZE = 200


async def _notify_user(user_id: int, message: str, *, parse_mode: str | None = None) -> bool:
    """Send without blocking the job on FloodWait (no send_queue in this build)."""
    try:
        kwargs = {}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        await Kenzo.send_message(user_id, message, **kwargs)
        return True
    except errors.FloodWaitError as e:
        logger.warning("low_volume notify FloodWait user=%s seconds=%s", user_id, e.seconds)
        return False
    except errors.InputUserDeactivatedError:
        await set_user_status(user_id, "DeleteAccount")
        return False
    except errors.UserIsBlockedError:
        await set_user_status(user_id, "BlockedBot")
        return False
    except Exception as e:
        logger.error("low_volume notify failed for %s: %s", user_id, e)
        return False


def _lite_service(service) -> SimpleNamespace:
    """Keep only fields needed for the low-volume sweep (drop full ORM retention)."""
    return SimpleNamespace(
        code=service.code,
        username=service.username,
        id=service.id,
        is_test=getattr(service, "is_test", False) is True,
        expiration_time=service.expiration_time,
        panel_userid=service.panel_userid,
        low_volume_notified=bool(getattr(service, "low_volume_notified", False)),
        in_panel=service.in_panel,
    )


async def _load_panel_username_map(service_crud: ServiceCRUD, panel_code: int) -> dict[str, list[SimpleNamespace]]:
    users: dict[str, list[SimpleNamespace]] = {}
    after_code = None
    while True:
        batch = await service_crud.get_all_services_by_panels_batch(
            [panel_code], limit=_BATCH_SIZE, after_code=after_code
        )
        if not batch:
            break
        for service in batch:
            if not service.username:
                continue
            users.setdefault(service.username, []).append(_lite_service(service))
        if len(batch) < _BATCH_SIZE:
            break
        after_code = batch[-1].code
    return users


async def check_low_volume():
    """Notify users when their remaining traffic is below 1GB."""
    start_time = time.time()
    logger.debug("%s check_low_volume started", LogTag.JOB)
    all_panels = await PanelsManager().get_all_panels()
    panels_without_webhook = [p for p in all_panels if not panel_webhook_notifications_enabled(p)]

    if not panels_without_webhook:
        logger.debug("%s check_low_volume: All panels have webhooks enabled, skipping cron job", LogTag.JOB)
        return

    logger.debug(f"{LogTag.JOB} check_low_volume: {len(panels_without_webhook)} panels without webhooks")

    service_crud = ServiceCRUD()
    exhausted_template = await get_bot_text(
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

    api_calls = 0
    notifications_sent = 0
    test_services_deleted = 0
    total_fetched = 0

    for panel in panels_without_webhook:
        users = await _load_panel_username_map(service_crud, panel.code)
        panel_service_count = sum(len(items) for items in users.values())
        total_fetched += panel_service_count
        if not users:
            continue

        logger.debug(
            f"{LogTag.JOB} check_low_volume: Checking panel {panel.name} with {len(users)} usernames "
            f"({panel_service_count} services)"
        )
        api = PasarguardAPI(panel.base_url)
        remaining_usernames = set(users)
        offset = 0

        while remaining_usernames:
            try:
                api_calls += 1
                resp = await api.get_users(
                    token=panel.cookie,
                    limit=_PAGE_SIZE,
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
                remaining_usernames.discard(user.username)

                remaining = (user.data_limit or 0) - (user.used_traffic or 0)
                for service in users[user.username]:
                    if service.is_test:
                        # Time-expired tests are cleaned only by handle_service_expiration.
                        if remaining > 0:
                            continue
                        try:
                            if service.panel_userid:
                                await api.remove_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
                        except Exception as e:
                            logger.warning(
                                f"{LogTag.JOB} check_low_volume: remove test user {service.username} from panel: {e}"
                            )
                        ok, _ = await service_crud.delete_service(service.code)
                        if ok:
                            test_services_deleted += 1
                            logger.info(
                                f"{LogTag.JOB} check_low_volume: deleted test service {service.code} "
                                f"(volume_exhausted=True)"
                            )
                            await _notify_user(
                                service.id,
                                f"کانفیگ تست شما با نام **{service.username}** به دلیل اتمام حجم پاک شد.",
                            )
                            await send_log_message(
                                LogType.OTHER,
                                message=(
                                    f"🧪 <b>کانفیگ تست پاک شد</b> (به دلیل اتمام حجم)\n\n"
                                    f"◾️ کد سرویس: <code>{service.code}</code>\n"
                                    f"◾️ اسم کانفیگ: <code>{service.username}</code>\n"
                                    f"◾️ شناسه کاربر: <code>{service.id}</code>\n"
                                    f"◾️ پنل: {panel.name}"
                                ),
                                parse_mode="html",
                            )
                        continue

                    if remaining <= 0:
                        if not service.low_volume_notified:
                            message = exhausted_template.replace("{service_code}", str(service.code)).replace(
                                "{config_name}", service.username
                            )
                            if await _notify_user(service.id, message, parse_mode="html"):
                                notifications_sent += 1
                                await service_crud.update_service(service.code, low_volume_notified=True)
                                service.low_volume_notified = True
                        continue

                    if remaining <= _LOW_VOLUME_BYTES and not service.low_volume_notified:
                        if await _notify_user(
                            service.id,
                            (
                                "**#Low_Data**\n"
                                "🔔 حجم باقی‌مانده‌ی سرویس شما: "
                                f"**{format_size(remaining, decimal_places=2)}**\n"
                                "برای جلوگیری از قطع سرویس، لطفاً پلن خود را تمدید یا ارتقا دهید.\n\n"
                                f"🔢 **کدسرویس**: `{service.code}`\n"
                                f"👤 **اسم کانفیگ**: `{service.username}`"
                            ),
                        ):
                            notifications_sent += 1
                            await service_crud.update_service(service.code, low_volume_notified=True)
                            service.low_volume_notified = True
                    elif remaining > _LOW_VOLUME_BYTES and service.low_volume_notified:
                        await service_crud.update_service(service.code, low_volume_notified=False)
                        service.low_volume_notified = False

            if not remaining_usernames:
                break
            offset += _PAGE_SIZE

        # Drop panel map before next panel to keep peak memory low.
        users.clear()

    elapsed = time.time() - start_time
    logger.info(
        f"{LogTag.JOB} check_low_volume | duration={elapsed:.2f}s, services={total_fetched}, "
        f"api={api_calls}, notify={notifications_sent}, test_deleted={test_services_deleted}"
    )

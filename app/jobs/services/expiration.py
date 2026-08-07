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
from app.utils.formatting.dates import timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size

logger = get_logger(__name__)


async def _notify_user(user_id: int, message: str, *, parse_mode: str = "html") -> bool:
    """Deliver a user notification without blocking the job on FloodWait.

    No send_queue in this build: try a direct send. Returns True only when the
    message was accepted so callers can safely set notify flags.
    """
    try:
        await Kenzo.send_message(user_id, message, parse_mode=parse_mode)
        return True
    except errors.FloodWaitError as e:
        # Do not sleep the job; leave notify flag unset so the next run retries.
        logger.warning("expiration notify FloodWait user=%s seconds=%s", user_id, e.seconds)
        return False
    except errors.InputUserDeactivatedError:
        await set_user_status(user_id, "DeleteAccount")
        return False
    except errors.UserIsBlockedError:
        await set_user_status(user_id, "BlockedBot")
        return False
    except Exception as e:
        logger.error("expiration notify failed for %s: %s", user_id, e)
        return False


async def cleanup_expired_test_services():
    """Immediately delete expired test services (no 3-day grace). Runs for all panels."""
    all_panels = await PanelsManager().get_all_panels()
    if not all_panels:
        return 0
    panels_by_code = {p.code: p for p in all_panels}
    panel_codes = list(panels_by_code)
    service_crud = ServiceCRUD()
    current_time = int(datetime.now().timestamp())
    batch_size = 500
    total_deleted = 0
    while True:
        # Always first page: deleting shrinks the result set; advancing a cursor can skip failed deletes.
        batch = await service_crud.get_expired_test_services_batch(
            panel_codes,
            current_time,
            limit=batch_size,
        )
        if not batch:
            break
        codes_to_delete: list[int] = []
        deleted_services = []
        for service in batch:
            panel = panels_by_code.get(service.in_panel) if service.in_panel else None
            if service.in_panel and service.panel_userid and panel:
                try:
                    api = PasarguardAPI(panel.base_url)
                    await api.remove_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
                except Exception as e:
                    logger.error("Failed to remove test service %s from panel: %s", service.username, e)
            codes_to_delete.append(service.code)
            deleted_services.append((service, panel))

        deleted_count = await service_crud.bulk_delete_services(codes_to_delete)
        total_deleted += deleted_count
        for service, panel in deleted_services:
            await _notify_user(
                service.id,
                f"کانفیگ تست شما با نام **{service.username}** به دلیل اتمام زمان پاک شد.",
                parse_mode="markdown",
            )
            panel_name = panel.name if panel else "—"
            log_msg = (
                f"🧪 <b>کانفیگ تست پاک شد</b> (به دلیل اتمام زمان)\n\n"
                f"◾️ کد سرویس: <code>{service.code}</code>\n"
                f"◾️ اسم کانفیگ: <code>{service.username}</code>\n"
                f"◾️ شناسه کاربر: <code>{service.id}</code>\n"
                f"◾️ پنل: {panel_name}"
            )
            await send_log_message(LogType.OTHER, message=log_msg, parse_mode="html")
        if len(batch) < batch_size:
            break
    if total_deleted:
        logger.info(f"{LogTag.JOB} cleanup_expired_test_services | deleted={total_deleted}")
    return total_deleted


async def cleanup_expired_paid_services(panel_codes: list[int], current_time: int) -> int:
    """
    Delete paid services expired 3+ days ago from panel and DB (all panels).
    Runs regardless of webhook so expired users are always cleaned.
    """
    if not panel_codes:
        return 0
    all_panels = await PanelsManager().get_all_panels()
    panels_by_code = {p.code: p for p in all_panels if p.code in set(panel_codes)}
    service_crud = ServiceCRUD()
    batch_size = 500
    deletions = 0
    while True:
        # Always first page while deleting — advancing a cursor can skip failed deletes.
        batch = await service_crud.get_services_expired_grace_period_batch(panel_codes, current_time, limit=batch_size)
        if not batch:
            break
        codes_to_delete: list[int] = []
        notify_items: list[tuple] = []
        for service in batch:
            user_info = None
            panel_info = panels_by_code.get(service.in_panel) if service.in_panel else None
            if service.in_panel and service.panel_userid and panel_info:
                try:
                    api = PasarguardAPI(panel_info.base_url)
                    try:
                        user_info = await api.get_user_by_id(
                            user_id=require_panel_userid(service), token=panel_info.cookie
                        )
                    except Exception as e:
                        logger.warning("Could not get user info for %s from panel: %s", service.username, e)
                    await api.remove_user_by_id(user_id=require_panel_userid(service), token=panel_info.cookie)
                except Exception as e:
                    logger.error("Failed to delete service %s from Marzban panel: %s", service.code, e)
            codes_to_delete.append(service.code)
            notify_items.append((service, panel_info, user_info))

        deleted_count = await service_crud.bulk_delete_services(codes_to_delete)
        deletions += deleted_count
        for service, panel_info, user_info in notify_items:
            await _notify_user(
                service.id,
                (
                    f"<b>#حذف_سرویس</b>\n\n"
                    f"<b>🚫 سرویس شما حذف شد</b>\n\n"
                    f"📋 <b>کد سرویس:</b> <code>{service.code}</code>\n"
                    f"👤 <b>نام کانفیگ:</b> <code>{service.username}</code>\n\n"
                    f"⚠️ <b>توضیحات:</b>\n"
                    f"سرویس شما به دلیل انقضای زمان و عدم تمدید پس از 3 روز از ربات حذف شد.\n\n"
                    f"💡 برای خرید سرویس جدید، از منوی اصلی ربات استفاده کنید.\n\n"
                    f"<b>#service_deleted_{service.code}</b>"
                ),
                parse_mode="html",
            )
            log_parts = [
                "✅ یک کانفیگ به دلیل انقضا پس از 3 روز حذف شد.\n\n",
                f"◾️ کد سرویس: <code>{service.code}</code>\n",
                f"◾️ شناسه کاربر: <code>{service.id}</code>\n",
                f"◾️ اسم کانفیگ: <code>{service.username}</code>\n",
            ]
            if panel_info:
                log_parts.append(f"◾️ پنل: {panel_info.name}\n")
            if service.expiration_time:
                log_parts.append(f"◾️ زمان انقضا: {timestamp_to_persian_expiry(service.expiration_time)}\n")
            if service.createtime:
                log_parts.append(f"◾️ زمان ایجاد: {timestamp_to_persian_expiry(service.createtime)}\n")
            log_parts.append(f"◾️ زمان حذف: {timestamp_to_persian_expiry(current_time)}\n")
            if user_info:
                used_traffic = getattr(user_info, "used_traffic", 0) or 0
                log_parts.append(f"◾️ حجم مصرفی: {format_size(used_traffic, decimal_places=2)}\n")
                if hasattr(user_info, "data_limit") and user_info.data_limit:
                    data_limit = user_info.data_limit
                    log_parts.append(f"◾️ حجم کل: {format_size(data_limit, decimal_places=2)}\n")
                    remaining = data_limit - used_traffic
                    if remaining > 0:
                        log_parts.append(f"◾️ حجم باقی‌مانده: {format_size(remaining, decimal_places=2)}\n")
                    else:
                        log_parts.append("◾️ حجم باقی‌مانده: 0 (تمام شده)\n")
                if hasattr(user_info, "expire") and user_info.expire:
                    log_parts.append(f"◾️ تاریخ انقضای مرزبان: {timestamp_to_persian_expiry(user_info.expire)}\n")
                if hasattr(user_info, "status") and user_info.status:
                    status_text = "فعال" if user_info.status == "active" else "غیرفعال"
                    log_parts.append(f"◾️ وضعیت مرزبان: {status_text}\n")
            elif service.package_size:
                log_parts.append(f"◾️ حجم پکیج: {format_size(service.package_size, decimal_places=2)}\n")
                log_parts.append("⚠️ اطلاعات مرزبان در دسترس نبود\n")
            await send_log_message(LogType.OTHER, message="".join(log_parts), parse_mode="html")
        if len(batch) < batch_size:
            break
    if deletions:
        logger.info(f"{LogTag.JOB} cleanup_expired_paid_services | deleted={deletions}")
    return deletions


async def handle_service_expiration():
    start_time = time.time()
    logger.debug("%s handle_service_expiration started", LogTag.JOB)

    service_crud = ServiceCRUD()
    current_time = int(datetime.now().timestamp())
    expiring_time = current_time + 24 * 60 * 60

    all_panels = await PanelsManager().get_all_panels()
    panels_without_webhook = [p for p in all_panels if not panel_webhook_notifications_enabled(p)]
    all_panel_codes = [p.code for p in all_panels]

    # Always run cleanup: test services + paid services expired 3+ days (all panels, regardless of webhook)
    await cleanup_expired_test_services()
    cleanup_deletions = await cleanup_expired_paid_services(all_panel_codes, current_time)

    if not panels_without_webhook:
        elapsed = time.time() - start_time
        logger.debug(
            f"{LogTag.JOB} handle_service_expiration: All panels have webhooks enabled, skipping notifications. "
            f"Cleanup deleted {cleanup_deletions} paid services. Elapsed: {elapsed:.2f}s"
        )
        return

    panel_codes_without_webhook = [p.code for p in panels_without_webhook]
    logger.debug(f"{LogTag.JOB} handle_service_expiration: {len(panels_without_webhook)} panels without webhooks")

    expiry_notifications = 0
    warning_notifications = 0
    services_checked = 0

    # Process in batches of 500 (paid services only; test services already cleaned)
    batch_size = 500
    after_expiration_time = None
    after_code = None
    total_processed = 0

    while True:
        batch = await service_crud.get_services_for_expiration_check_batch(
            panel_codes_without_webhook,
            current_time,
            expiring_time,
            limit=batch_size,
            after_expiration_time=after_expiration_time,
            after_code=after_code,
        )

        if not batch:
            break

        logger.debug(
            f"{LogTag.JOB} handle_service_expiration: Processing batch size={len(batch)} "
            f"after=({after_expiration_time},{after_code})"
        )
        total_processed += len(batch)

        for service in batch:
            is_test = getattr(service, "is_test", False) is True
            services_checked += 1
            if service.warning_time is None:
                service.warning_time = 0
            if service.warning is None:
                service.warning = 0
            if (
                service.expiration_time
                and current_time < service.expiration_time <= expiring_time
                and not service.expire_notified
            ):
                time_diff_seconds = service.expiration_time - current_time
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

                message = (
                    f"<b>#اطلاع_رسانی</b>\n\n"
                    f"<b>#⃣ کد سرویس(در ربات): {service.code}</b>\n"
                    f"<b>🔷 اسم کانفیگ: {service.username}</b>\n"
                    f"<b>⌛️ سرویس شما تا {time_text} دیگر منقضی می‌شود.</b>\n"
                    f"<b>👈🏻 شما می‌توانید سرویس خود را در بخش (سرویس های من) تمدید کنید.</b>\n\n"
                    f"<b>#notification_{service.code}</b>"
                )
                if await _notify_user(service.id, message, parse_mode="html"):
                    expiry_notifications += 1
                    await service_crud.update_service(service.code, expire_notified=True)
                    await send_log_message(LogType.OTHER, message=message, parse_mode="html")

            # Paid-only: grace-period warning after expiry (tests are deleted immediately).
            if (
                not is_test
                and service.expiration_time
                and service.expiration_time <= current_time
                and service.warning == 0
            ):
                days_remaining = 3
                warn_text = (
                    f"<b>#اطلاع_رسانی</b>\n\n"
                    f"<b>#⃣ کد سرویس(در ربات): {service.code}</b>\n"
                    f"<b>🔷 اسم کانفیگ: {service.username}</b>\n"
                    f"<b>📅 سرویس شما به دلیل انقضا غیرفعال شده است.</b>\n"
                    f"<b>👈🏻 شما می‌توانید سرویس خود را در بخش (سرویس های من) تمدید کنید.</b>\n"
                    f"<b>⚠️ نکته: اگر در {days_remaining} روز آینده تمدید نکنید، سرویس شما حذف خواهد شد.</b>\n\n"
                    f"<b>#notification_{service.code}</b>"
                )
                if await _notify_user(service.id, warn_text, parse_mode="html"):
                    await service_crud.update_service(service.code, warning=1, warning_time=current_time)
                    warning_notifications += 1
                    await send_log_message(LogType.OTHER, message=warn_text, parse_mode="html")

        last = batch[-1]
        after_expiration_time = last.expiration_time
        after_code = last.code
        if len(batch) < batch_size:
            break

    elapsed = time.time() - start_time
    total_deletions = cleanup_deletions
    logger.info(
        f"{LogTag.JOB} handle_service_expiration | duration={elapsed:.2f}s, "
        f"total={total_processed}, checked={services_checked}, "
        f"expiry_notify={expiry_notifications}, warn_notify={warning_notifications}, deleted={total_deletions}"
    )

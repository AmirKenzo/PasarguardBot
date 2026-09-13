"""Callback handlers for admin bulk_increase."""

import asyncio
import time
from datetime import datetime
from typing import Any

from pasarguard import BulkUser, PasarguardAPI, PermissionScope, UserModify
from telethon import events

from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.logger import LogType, get_logger
from app.services.billing.renewal import require_panel_userid
from app.telegram.admin.bulk_increase import keyboards, states, texts
from app.telegram.keyboards.admin import Panel_Admin_Buttons
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.state import delete_data, get_data, set_data, set_step
from app.utils.formatting.conversions import day_to_timestamp, gigabytes_to_bytes
from config import ADMIN_ID

logger = get_logger(__name__)


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _permission_scope_value(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(PermissionScope.ALL if value else PermissionScope.NONE)
    if isinstance(value, PermissionScope):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        nested = value.get("scope", value.get("value", 0))
        return _permission_scope_value(nested)

    nested = _field(value, "scope")
    if nested is not None:
        return _permission_scope_value(nested)

    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _admin_bulk_strategy(admin: Any) -> tuple[bool, str, str]:
    role = _field(admin, "role")
    if bool(_field(admin, "is_owner", False) or _field(role, "is_owner", False)):
        return True, "bulk", "مالک کامل پنل است؛ عملیات با bulk پاسارگارد انجام می‌شود."

    permissions = _field(role, "permissions")
    users_permissions = _field(permissions, "users")
    admins_permissions = _field(permissions, "admins")
    users_update_scope = _permission_scope_value(_field(users_permissions, "update"))
    admins_read_simple = bool(_field(admins_permissions, "read_simple", False))

    if users_update_scope >= int(PermissionScope.ALL) and admins_read_simple:
        return True, "bulk", "دسترسی users.update=all و admins.read_simple=true تایید شد؛ bulk فعال است."

    missing = []
    if users_update_scope < int(PermissionScope.ALL):
        missing.append("users.update = all")
    if not admins_read_simple:
        missing.append("admins.read_simple = true")

    return False, "manual", "دسترسی کافی برای bulk ندارد: " + " و ".join(missing)


def _exception_detail(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        try:
            payload = response.json()
            detail = payload.get("detail") if isinstance(payload, dict) else payload
        except Exception:
            detail = getattr(response, "text", "")
        if detail:
            return f"HTTP {status_code}: {detail}" if status_code else str(detail)
    return str(exc) or exc.__class__.__name__


def _preflight_exception_detail(exc: Exception) -> str:
    detail = _exception_detail(exc)
    lower_detail = detail.lower()

    if "temporary failure in name resolution" in lower_detail or "name or service not known" in lower_detail:
        return "خطای DNS/اتصال: دامنه یا آدرس پنل از سمت سرور بات پیدا نشد."

    if "permission denied: users.update requires scope=all" in lower_detail:
        return "دسترسی users.update باید روی all باشد."

    if "permission denied: admins.read_simple" in lower_detail:
        return "دسترسی admins.read_simple باید فعال باشد."

    return texts.shorten(detail, 160)


def _bulk_trackable_services(services: list, issues: list[str], panel_label: str) -> tuple[list, int]:
    valid_services = []
    skipped = 0

    for service in services:
        if not service.username:
            skipped += 1
            texts.remember_issue(issues, f"{panel_label} / سرویس {service.code}: username خالی است.")
            continue
        valid_services.append(service)

    return valid_services, skipped


async def _safe_edit(event: events.CallbackQuery.Event | None, text: str, buttons=None) -> None:
    # event is None when the run was started from the web panel: no message to edit.
    if event is None:
        return
    try:
        await event.edit(text, buttons=buttons)
    except Exception as exc:
        logger.debug("Bulk increase progress edit skipped: %s", exc)


async def clear_bulk_increase_steps(admin_id: int) -> None:
    for key in states.STEP_KEYS:
        await delete_data(admin_id, key)
    await set_step(admin_id, states.PANEL_STEP)


async def _resolve_bulk_panels(panel_code_str: str | None) -> list:
    if panel_code_str == "all":
        return await PanelsManager().get_all_panels_reverse()
    if panel_code_str:
        panel = await PanelsManager().get_panel_by_code(code=int(panel_code_str))
        return [panel] if panel else []
    return []


async def _get_panel_strategy(panel) -> dict:
    api = PasarguardAPI(base_url=panel.base_url)
    try:
        admin = await api.get_current_admin(token=panel.cookie)
        can_bulk, mode, reason = _admin_bulk_strategy(admin)
        admin_id = _field(admin, "id")
        if can_bulk and admin_id is None:
            can_bulk = False
            mode = "manual"
            reason = "شناسه عددی ادمین از /api/admin دریافت نشد؛ حالت معمولی اجرا می‌شود."
        return {
            "panel_code": panel.code,
            "can_bulk": can_bulk,
            "mode": mode,
            "reason": reason,
            "admin_id": admin_id,
            "admin_username": _field(admin, "username", "نامشخص"),
        }
    except Exception as exc:
        return {
            "panel_code": panel.code,
            "can_bulk": False,
            "mode": "manual",
            "reason": f"بررسی /api/admin ناموفق بود: {_preflight_exception_detail(exc)}",
            "admin_id": None,
            "admin_username": "نامشخص",
        }
    finally:
        await api.close()


async def _load_panel_jobs(panels: list) -> list[dict]:
    jobs = []
    service_crud = ServiceCRUD()
    for panel in panels:
        services = await service_crud.get_panel_active_services(panel.code)
        jobs.append({"panel": panel, "services": services})
    return jobs


def _job_valid_count(job: dict, *, bulk: bool = False) -> int:
    if bulk:
        return sum(1 for service in job["services"] if service.username)
    return sum(1 for service in job["services"] if service.username and service.panel_userid)


async def _maybe_update_progress(
    event: events.CallbackQuery.Event,
    state: dict,
    issues: list[str],
    *,
    force: bool = False,
) -> None:
    now = time.monotonic()
    if not force and now - state["last_edit_at"] < states.PROGRESS_EDIT_INTERVAL:
        return
    state["last_edit_at"] = now
    await _safe_edit(event, texts.build_progress_message(state, issues), buttons=None)


async def _process_panel_with_bulk(
    event: events.CallbackQuery.Event,
    panel,
    services: list,
    strategy: dict,
    volume_bytes: int,
    time_days: int,
    state: dict,
    issues: list[str],
) -> None:
    panel_label = texts.panel_label(panel)
    state["current_panel"] = f"{panel_label} (bulk)"
    admin_id = strategy.get("admin_id")
    if admin_id is None:
        texts.remember_issue(issues, f"{panel_label}: شناسه ادمین برای bulk موجود نیست؛ ادامه با حالت معمولی.")
        await _process_panel_manually(event, panel, services, volume_bytes, time_days, state, issues)
        return

    valid_services, skipped = _bulk_trackable_services(services, issues, panel_label)
    state["skipped"] += skipped

    if not valid_services:
        await _maybe_update_progress(event, state, issues, force=True)
        return

    expire_seconds = time_days * 86400 if time_days else 0
    api = PasarguardAPI(base_url=panel.base_url)
    try:
        if volume_bytes:
            await api.bulk_modify_users_datalimit(
                BulkUser(dry_run=True, admins=[admin_id], amount=volume_bytes),
                token=panel.cookie,
            )
        if expire_seconds:
            await api.bulk_modify_users_expire(
                BulkUser(dry_run=True, admins=[admin_id], amount=expire_seconds),
                token=panel.cookie,
            )
    except Exception as exc:
        texts.remember_issue(
            issues,
            f"{panel_label}: dry-run bulk رد شد؛ ادامه با حالت معمولی - {_exception_detail(exc)}",
        )
        logger.warning("Bulk dry-run failed for panel %s, falling back to manual: %s", panel.code, exc)
        await api.close()
        await _process_panel_manually(event, panel, valid_services, volume_bytes, time_days, state, issues)
        return

    try:
        if volume_bytes:
            await api.bulk_modify_users_datalimit(
                BulkUser(admins=[admin_id], amount=volume_bytes),
                token=panel.cookie,
            )
        if expire_seconds:
            await api.bulk_modify_users_expire(
                BulkUser(admins=[admin_id], amount=expire_seconds),
                token=panel.cookie,
            )
    except Exception as exc:
        failed = len(valid_services)
        state["failed"] += failed
        state["processed"] += failed
        texts.remember_issue(issues, f"{panel_label}: خطای bulk - {_exception_detail(exc)}")
        logger.error("Bulk increase failed for panel %s: %s", panel.code, exc)
        await _maybe_update_progress(event, state, issues, force=True)
        return
    finally:
        await api.close()

    now_ts = int(datetime.now().timestamp())
    updates = []
    volume_delta = 0
    for service in valid_services:
        fields = {}
        if volume_bytes:
            current_package_size = int(service.package_size or 0)
            next_package_size = max(0, current_package_size + volume_bytes)
            fields["package_size"] = next_package_size
            volume_delta += next_package_size - current_package_size
        if expire_seconds:
            current_expire = texts.timestamp_or_none(service.expiration_time) or now_ts
            fields["expiration_time"] = current_expire + expire_seconds
        if fields:
            updates.append((service.code, fields))

    matched, updated = await ServiceCRUD().bulk_update_services(updates)
    if updated != len(updates):
        texts.remember_issue(
            issues,
            f"{panel_label}: bulk پنل موفق بود اما DB کامل آپدیت نشد ({updated}/{len(updates)}، matched={matched}).",
        )

    success = len(valid_services)
    state["success"] += success
    state["processed"] += success
    if volume_bytes:
        state["total_volume_added"] += volume_delta
    if time_days:
        state["total_time_added"] += time_days * success
    state["affected_users"].update(service.id for service in valid_services if service.id)
    await _maybe_update_progress(event, state, issues, force=True)


async def _process_panel_manually(
    event: events.CallbackQuery.Event,
    panel,
    services: list,
    volume_bytes: int,
    time_days: int,
    state: dict,
    issues: list[str],
) -> None:
    panel_label = texts.panel_label(panel)
    state["current_panel"] = f"{panel_label} (معمولی)"
    api = PasarguardAPI(base_url=panel.base_url)

    try:
        for service in services:
            if not service.username:
                state["skipped"] += 1
                texts.remember_issue(issues, f"{panel_label} / سرویس {service.code}: username خالی است.")
                await _maybe_update_progress(event, state, issues)
                continue
            if not service.panel_userid:
                state["skipped"] += 1
                texts.remember_issue(issues, f"{panel_label} / {service.username}: panel_userid سینک نشده است.")
                await _maybe_update_progress(event, state, issues)
                continue

            try:
                panel_userid = require_panel_userid(service)
                current_user = await api.get_user_by_id(user_id=panel_userid, token=panel.cookie)
                current_data_limit = int(current_user.data_limit) if current_user.data_limit else 0
                current_expire = texts.timestamp_or_none(current_user.expire)
                if current_user.expire and current_expire is None:
                    texts.remember_issue(
                        issues,
                        f"{panel_label} / {service.username}: expire قابل تبدیل نبود: {current_user.expire}",
                    )

                new_data_limit = max(0, current_data_limit + volume_bytes) if volume_bytes else None
                volume_delta = (new_data_limit - current_data_limit) if new_data_limit is not None else 0
                new_expire = None
                if time_days:
                    new_expire = current_expire + (time_days * 86400) if current_expire else day_to_timestamp(time_days)

                await api.modify_user_by_id(
                    user_id=panel_userid,
                    user=UserModify(data_limit=new_data_limit, expire=new_expire),
                    token=panel.cookie,
                )

                db_fields = {}
                if new_data_limit is not None:
                    db_fields["package_size"] = new_data_limit
                if new_expire is not None:
                    db_fields["expiration_time"] = new_expire

                update_result = await ServiceCRUD().update_service(code=service.code, **db_fields)
                if isinstance(update_result, tuple) and not update_result[0]:
                    texts.remember_issue(issues, f"{panel_label} / {service.username}: خطای DB - {update_result[1]}")
                    logger.warning("Failed to update service %s in database: %s", service.code, update_result[1])

                state["success"] += 1
                state["processed"] += 1
                if volume_bytes:
                    state["total_volume_added"] += volume_delta
                if time_days:
                    state["total_time_added"] += time_days
                if service.id:
                    state["affected_users"].add(service.id)

                await asyncio.sleep(0.1)
            except Exception as exc:
                state["failed"] += 1
                state["processed"] += 1
                detail = _exception_detail(exc)
                texts.remember_issue(issues, f"{panel_label} / {service.username or service.code}: {detail}")
                logger.error("Error updating service %s: %s", service.code, exc)

            await _maybe_update_progress(event, state, issues)
    finally:
        await api.close()

    await _maybe_update_progress(event, state, issues, force=True)


async def _run_bulk_increase(
    event: events.CallbackQuery.Event | None,
    panels: list,
    volume: str | None,
    time_days_raw: str | None,
    panel_text: str,
    *,
    actor_id: int | None = None,
) -> dict:
    volume_text, time_text = texts.operation_texts(volume, time_days_raw)
    volume_bytes = gigabytes_to_bytes(float(volume)) if volume else 0
    time_days = int(time_days_raw) if time_days_raw else 0
    issues: list[str] = []

    jobs = await _load_panel_jobs(panels)
    strategies = {}
    for panel in panels:
        strategies[panel.code] = await _get_panel_strategy(panel)

    bulk_panels = sum(1 for strategy in strategies.values() if strategy["can_bulk"])
    manual_panels = len(panels) - bulk_panels
    if bulk_panels and manual_panels:
        mode_text = f"{bulk_panels} پنل bulk، {manual_panels} پنل معمولی"
    elif bulk_panels:
        mode_text = "bulk پاسارگارد"
    else:
        mode_text = "معمولی تک‌به‌تک"

    state = {
        "panel_text": panel_text,
        "panel_count": len(panels),
        "volume_text": volume_text,
        "time_text": time_text,
        "mode_text": mode_text,
        "total": sum(
            _job_valid_count(job, bulk=bool(strategies.get(job["panel"].code, {}).get("can_bulk"))) for job in jobs
        ),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total_volume_added": 0,
        "total_time_added": 0,
        "affected_users": set(),
        "current_panel": "-",
        "last_edit_at": 0.0,
    }

    await _maybe_update_progress(event, state, issues, force=True)

    for job in jobs:
        panel = job["panel"]
        strategy = strategies.get(panel.code, {})
        if strategy.get("can_bulk"):
            await _process_panel_with_bulk(
                event, panel, job["services"], strategy, volume_bytes, time_days, state, issues
            )
        else:
            await _process_panel_manually(event, panel, job["services"], volume_bytes, time_days, state, issues)

    if actor_id is None and event is not None:
        actor_id = event.sender_id
    if event is not None:
        await clear_bulk_increase_steps(event.sender_id)
    await _safe_edit(event, texts.build_result_message(state, issues), buttons=Panel_Admin_Buttons)
    await send_log_message(LogType.OTHER, message=texts.build_log_message(state, actor_id))
    return {**state, "issues": issues, "affected_users": len(state["affected_users"])}


def bulk_increase_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    if not event.data:
        return False
    data = event.data.decode("UTF-8")
    if data.startswith(states.BULK_INCREASE_PANEL_PREFIX):
        return True
    return data.startswith("bulk_increase_")


async def bulk_increase_callback_handler(event: events.CallbackQuery.Event):
    """Handle bulk increase volume and time callbacks"""
    if not event.is_private:
        return

    data = event.data.decode("UTF-8")

    if data.startswith(states.BULK_INCREASE_PANEL_PREFIX):
        panel_code_str = data.split(":")[1]
        await set_data(event.sender_id, states.STEP_KEY_PANEL, panel_code_str)
        await event.edit(
            texts.initial_settings_menu_text(panel_code_str),
            buttons=keyboards.settings_menu_buttons(),
        )

    elif data == states.BULK_INCREASE_SET_VOLUME:
        await set_data(event.sender_id, states.STEP_KEY_STEP, "volume")
        await set_step(event.sender_id, states.BULK_INCREASE_VOLUME_STEP)
        sent_msg = await event.edit(
            texts.VOLUME_SET_PROMPT,
            buttons=keyboards.volume_input_back_button(),
        )
        if sent_msg:
            await set_data(event.sender_id, states.STEP_KEY_LAST_MSG_ID, str(sent_msg.id))

    elif data == states.BULK_INCREASE_SET_TIME:
        await set_data(event.sender_id, states.STEP_KEY_STEP, "time")
        await set_step(event.sender_id, states.BULK_INCREASE_TIME_STEP)
        sent_msg = await event.edit(
            texts.TIME_SET_PROMPT,
            buttons=keyboards.volume_input_back_button(),
        )
        if sent_msg:
            await set_data(event.sender_id, states.STEP_KEY_LAST_MSG_ID, str(sent_msg.id))

    elif data == states.BULK_INCREASE_BACK:
        panel_code_str = await get_data(event.sender_id, states.STEP_KEY_PANEL)
        volume = await get_data(event.sender_id, states.STEP_KEY_VOLUME)
        time_days = await get_data(event.sender_id, states.STEP_KEY_TIME)
        volume_text, time_text = texts.operation_texts(volume, time_days)
        await event.edit(
            texts.settings_menu_text(panel_code_str, volume_text, time_text),
            buttons=keyboards.settings_menu_buttons(),
        )

    elif data == states.BULK_INCREASE_CANCEL:
        await clear_bulk_increase_steps(event.sender_id)
        await event.edit(texts.CANCELLED_TEXT, buttons=Panel_Admin_Buttons)

    elif data == states.BULK_INCREASE_CONFIRM:
        panel_code_str = await get_data(event.sender_id, states.STEP_KEY_PANEL)
        volume = await get_data(event.sender_id, states.STEP_KEY_VOLUME)
        time_days = await get_data(event.sender_id, states.STEP_KEY_TIME)

        if not volume and not time_days:
            await event.answer(texts.MIN_SETTING_REQUIRED_ALERT, alert=True)
            return

        panels = await _resolve_bulk_panels(panel_code_str)
        if not panels:
            await event.edit(texts.NO_PANELS_ERROR, buttons=Panel_Admin_Buttons)
            return

        panel_text = texts.panel_scope_text(panel_code_str, len(panels))
        volume_text, time_text = texts.operation_texts(volume, time_days)

        await event.edit(
            texts.PREFLIGHT_CHECKING_TEXT.format(
                panel_text=panel_text,
                volume_text=volume_text,
                time_text=time_text,
            ),
            buttons=None,
        )

        jobs = await _load_panel_jobs(panels)
        strategies = {}
        for panel in panels:
            strategies[panel.code] = await _get_panel_strategy(panel)

        preflight_message = texts.build_preflight_message(
            panels=panels,
            jobs=jobs,
            strategies=strategies,
            volume_text=volume_text,
            time_text=time_text,
            panel_text=panel_text,
            job_valid_count=_job_valid_count,
        )
        target_services = sum(
            _job_valid_count(job, bulk=bool(strategies.get(job["panel"].code, {}).get("can_bulk"))) for job in jobs
        )
        buttons = None
        if target_services > 0:
            buttons = keyboards.preflight_buttons()
        await event.edit(preflight_message, buttons=buttons or Panel_Admin_Buttons)

    elif data == states.BULK_INCREASE_APPLY:
        panel_code_str = await get_data(event.sender_id, states.STEP_KEY_PANEL)
        volume = await get_data(event.sender_id, states.STEP_KEY_VOLUME)
        time_days = await get_data(event.sender_id, states.STEP_KEY_TIME)

        if not volume and not time_days:
            await event.answer(texts.MIN_SETTING_REQUIRED_ALERT, alert=True)
            return

        panels = await _resolve_bulk_panels(panel_code_str)
        if not panels:
            await event.edit(texts.NO_PANELS_ERROR, buttons=Panel_Admin_Buttons)
            return

        panel_text = texts.panel_scope_text(panel_code_str, len(panels))
        await _run_bulk_increase(event, panels, volume, time_days, panel_text)


def register(client):
    client.add_event_handler(
        bulk_increase_callback_handler,
        events.CallbackQuery(func=bulk_increase_callback_filter),
    )

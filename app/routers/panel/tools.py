"""System status, database backup and bulk volume/time increase."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request

from app.db.base import DATABASE_DIALECT
from app.jobs.scheduler import scheduler
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.services import PanelPanelOption
from app.models.panel.tools import (
    PanelBulkIncreaseRequest,
    PanelScheduledJob,
    PanelSystemMetrics,
    PanelToolsResponse,
    PanelVersions,
)
from app.panel import audit, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.backup import create_backup_zip, run_backup_and_send
from app.telegram.admin.bulk_increase.callbacks import _resolve_bulk_panels, _run_bulk_increase
from app.telegram.admin.info_bot.service import _collect_system_metrics
from app.version import VERSIONS

log = get_logger(__name__)
router = APIRouter()

ALL_PANELS = "all"

# Background jobs are kept here so the event loop cannot garbage-collect a task
# that is still running.
_background_tasks: set[asyncio.Task] = set()


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        ip=actor.ip,
        **kwargs,
    )


@router.post("/panel/tools", response_model=PanelToolsResponse)
async def tools_overview(payload: PanelRequest, request: Request) -> PanelToolsResponse:
    async def handle(_: PanelActor) -> PanelToolsResponse:
        metrics, panels = await asyncio.gather(
            asyncio.to_thread(_collect_system_metrics),
            queries.list_panels(),
        )
        jobs: list[PanelScheduledJob] = []
        try:
            jobs = [
                PanelScheduledJob(id=str(job.id), next_run=str(job.next_run_time) if job.next_run_time else None)
                for job in scheduler.get_jobs()
            ]
        except Exception as exc:
            log.debug("panel: could not read scheduler jobs: %s", exc)

        return PanelToolsResponse(
            metrics=PanelSystemMetrics(
                **{key: metrics[key] for key in PanelSystemMetrics.model_fields if key in metrics}
            ),
            versions=PanelVersions(
                app=VERSIONS.app,
                telethon=VERSIONS.telethon,
                telethon_layer=str(VERSIONS.telethon_layer),
                fastapi=VERSIONS.fastapi,
                pasarguard=VERSIONS.pasarguard,
                database=DATABASE_DIALECT,
            ),
            jobs=jobs,
            panels=[PanelPanelOption(code=int(panel.code), name=panel.name) for panel in panels],
            backup_supported=DATABASE_DIALECT == "mysql",
        )

    return await guard.run(payload, request, PanelToolsResponse, handle)


@router.post("/panel/tools/backup/send", response_model=ActionResponse)
async def backup_send(payload: PanelRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        result = await run_backup_and_send(trigger="panel")
        await _log(
            actor,
            "backup_send",
            target_type="backup",
            detail={"ok": bool(result.ok), "message": result.message},
        )
        if not result.ok:
            return ActionResponse(ok=False, error=result.message or "ساخت بکاپ انجام نشد.")
        return ActionResponse(message="بکاپ ساخته و به کانال لاگ ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/tools/backup/send-to-me", response_model=ActionResponse)
async def backup_send_to_admin(payload: PanelRequest, request: Request) -> ActionResponse:
    """Build the zip and send it to the requesting admin's private chat.

    The archive carries the database dump and the ``.env`` file, so it goes out
    over Telegram to the admin who asked for it rather than as an HTTP download.
    """

    async def handle(actor: PanelActor) -> ActionResponse:
        from app import Kenzo

        if not Kenzo.is_connected():
            return ActionResponse(ok=False, error="ربات به تلگرام متصل نیست.")

        temp_dir = Path(await asyncio.to_thread(tempfile.mkdtemp, "pasarguardbot-panel-backup-"))
        try:
            zip_path = await create_backup_zip(temp_dir)
            await Kenzo.send_file(actor.user_id, str(zip_path), force_document=True)
        except Exception as exc:
            log.error("panel: backup delivery failed: %s", exc, exc_info=True)
            return ActionResponse(ok=False, error="ساخت یا ارسال بکاپ انجام نشد.")
        finally:
            await asyncio.to_thread(shutil.rmtree, temp_dir, True)

        await _log(actor, "backup_send_admin", target_type="backup", detail={"file": zip_path.name})
        return ActionResponse(message="بکاپ در چت خصوصی ربات برایت ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


async def _run_bulk_in_background(actor: PanelActor, panels, volume, days, label) -> None:
    try:
        state = await _run_bulk_increase(None, panels, volume, days, label, actor_id=actor.user_id)
        detail = {
            "panels": label,
            "volume": volume,
            "days": days,
            "success": state.get("success"),
            "failed": state.get("failed"),
            "skipped": state.get("skipped"),
        }
        action = "bulk_increase_done"
    except Exception as exc:
        log.error("panel: bulk increase failed: %s", exc, exc_info=True)
        detail = {"panels": label, "volume": volume, "days": days, "error": str(exc)[:300]}
        action = "bulk_increase_failed"

    await _log(actor, action, target_type="bulk_increase", detail=detail)


@router.post("/panel/tools/bulk-increase", response_model=ActionResponse)
async def bulk_increase(payload: PanelBulkIncreaseRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if not payload.confirm:
            return ActionResponse(ok=False, error="برای اجرا باید تأیید کنی.")
        if payload.volume_gb is None and payload.days is None:
            return ActionResponse(ok=False, error="حداقل یکی از حجم یا زمان را وارد کن.")

        panel_code = ALL_PANELS if payload.panel == ALL_PANELS else str(payload.panel).strip()
        if panel_code != ALL_PANELS and not panel_code.isdigit():
            return ActionResponse(ok=False, error="کد پنل معتبر نیست.")

        target_panels = await _resolve_bulk_panels(panel_code)
        if not target_panels:
            return ActionResponse(ok=False, error="پنلی برای این عملیات پیدا نشد.")

        volume = f"{payload.volume_gb:g}" if payload.volume_gb is not None else None
        days = str(payload.days) if payload.days is not None else None
        label = ALL_PANELS if panel_code == ALL_PANELS else str(target_panels[0].name)

        await _log(
            actor,
            "bulk_increase_start",
            target_type="bulk_increase",
            detail={"panels": label, "volume": volume, "days": days},
        )

        task = asyncio.create_task(_run_bulk_in_background(actor, target_panels, volume, days, label))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return ActionResponse(message="افزایش گروهی در پس‌زمینه شروع شد؛ نتیجه در گزارش فعالیت ثبت می‌شود.")

    return await guard.run(payload, request, ActionResponse, handle)

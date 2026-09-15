"""Broadcast jobs: compose, start, pause, resume and cancel.

Uses the bot's own broadcast manager, so jobs behave exactly like the ones
created from Telegram.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.crud.broadcast import BroadcastJobCRUD
from app.logger import get_logger
from app.models.panel.broadcast import (
    TARGET_MODES,
    PanelBroadcastJobRequest,
    PanelBroadcastJobRow,
    PanelBroadcastResponse,
    PanelBroadcastSendRequest,
)
from app.models.panel.common import ActionResponse, PanelRequest
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.broadcast import broadcast_manager

log = get_logger(__name__)
router = APIRouter()

FINISHED_STATUSES = ("done", "canceled", "failed")


async def _log(actor: PanelActor, action: str, job_id: int, **kwargs) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        target_type="broadcast",
        target_id=job_id,
        ip=actor.ip,
        **kwargs,
    )


@router.post("/panel/broadcast", response_model=PanelBroadcastResponse)
async def broadcast_overview(payload: PanelRequest, request: Request) -> PanelBroadcastResponse:
    async def handle(_: PanelActor) -> PanelBroadcastResponse:
        jobs = await BroadcastJobCRUD().get_incomplete_jobs()
        return PanelBroadcastResponse(
            jobs=[
                PanelBroadcastJobRow(
                    id=int(job.id),
                    text=str((job.payload_json or {}).get("text") or ""),
                    target_mode=job.target_mode,
                    total_targets=int(job.total_targets or 0),
                    sent_ok=int(job.sent_ok or 0),
                    sent_fail=int(job.sent_fail or 0),
                    status=job.status,
                    created_at=job.created_at,
                    can_pause=job.status == "running",
                    can_resume=job.status == "paused",
                    can_cancel=job.status not in FINISHED_STATUSES,
                )
                for job in jobs
            ]
        )

    return await guard.run(payload, request, PanelBroadcastResponse, handle)


@router.post("/panel/broadcast/send", response_model=ActionResponse)
async def broadcast_send(payload: PanelBroadcastSendRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        text = payload.text.strip()[:4000]
        if not text:
            return ActionResponse(ok=False, error="متن پیام خالی است.")
        target_mode = payload.target_mode if payload.target_mode in TARGET_MODES else "all"

        job_id = await broadcast_manager.create_job(
            created_by=actor.user_id,
            target_mode=target_mode,
            payload_json={"text": text},
            delay_ms=payload.delay_ms,
            batch_size=payload.batch_size,
            batch_delay_ms=payload.batch_delay_ms,
        )
        if not job_id:
            return ActionResponse(ok=False, error="ساخت این ارسال ممکن نشد.")

        await BroadcastJobCRUD().update_job(job_id, status="queued")
        started, message = await broadcast_manager.confirm_start(job_id)
        if not started:
            log.info("panel: broadcast %s queued but not started now: %s", job_id, message)

        await _log(actor, "broadcast_create", job_id, detail={"target_mode": target_mode, "length": len(text)})
        return ActionResponse(message="ارسال در صف قرار گرفت.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/broadcast/pause", response_model=ActionResponse)
async def broadcast_pause(payload: PanelBroadcastJobRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok, _message = await broadcast_manager.pause_job(payload.job_id)
        await _log(actor, "broadcast_pause", payload.job_id)
        if not ok:
            return ActionResponse(ok=False, error="این ارسال قابل توقف نیست.")
        return ActionResponse(message="ارسال متوقف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/broadcast/resume", response_model=ActionResponse)
async def broadcast_resume(payload: PanelBroadcastJobRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok, _message = await broadcast_manager.resume_job(payload.job_id)
        await _log(actor, "broadcast_resume", payload.job_id)
        if not ok:
            return ActionResponse(ok=False, error="این ارسال قابل ادامه دادن نیست.")
        return ActionResponse(message="ارسال ادامه یافت.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/broadcast/cancel", response_model=ActionResponse)
async def broadcast_cancel(payload: PanelBroadcastJobRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok, _message = await broadcast_manager.cancel_job(payload.job_id)
        await _log(actor, "broadcast_cancel", payload.job_id)
        if not ok:
            return ActionResponse(ok=False, error="این ارسال قابل لغو نیست.")
        return ActionResponse(message="ارسال لغو شد.")

    return await guard.run(payload, request, ActionResponse, handle)

"""Panel activity log."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request

from app.models.panel.common import page_meta
from app.models.panel.reports import PanelAuditRequest, PanelAuditResponse, PanelAuditRow
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


def _detail(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return {"text": raw[:160]}
    return data if isinstance(data, dict) else {"text": str(data)[:160]}


@router.post("/panel/audit", response_model=PanelAuditResponse)
async def list_audit(payload: PanelAuditRequest, request: Request) -> PanelAuditResponse:
    async def handle(_: PanelActor) -> PanelAuditResponse:
        (rows, total), actions = await asyncio.gather(
            audit.list_entries(
                page=payload.page,
                limit=payload.limit,
                action=payload.action.strip(),
                admin_id=payload.admin_id,
            ),
            audit.known_actions(),
        )
        return PanelAuditResponse(
            entries=[
                PanelAuditRow(
                    id=int(entry.id),
                    admin_id=entry.admin_id,
                    admin_username=entry.admin_username,
                    action=entry.action,
                    target_type=entry.target_type,
                    target_id=entry.target_id,
                    detail=_detail(entry.detail),
                    ip=entry.ip,
                    created_at=entry.created_at,
                )
                for entry in rows
            ],
            actions=actions,
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelAuditResponse, handle)

"""Sold services: list, filter, enable/disable, delete."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request

from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.services import (
    PanelPanelOption,
    PanelServiceDeleteRequest,
    PanelServiceRow,
    PanelServicesRequest,
    PanelServicesResponse,
    PanelServiceToggleRequest,
)
from app.panel import mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


@router.post("/panel/services", response_model=PanelServicesResponse)
async def list_services(payload: PanelServicesRequest, request: Request) -> PanelServicesResponse:
    async def handle(_: PanelActor) -> PanelServicesResponse:
        (rows, total), panels = await asyncio.gather(
            queries.list_services(
                q=payload.q.strip(),
                panel=payload.panel,
                state=payload.state,
                page=payload.page,
                per_page=payload.limit,
            ),
            queries.panel_names(),
        )
        now = int(time.time())
        return PanelServicesResponse(
            services=[
                PanelServiceRow(
                    code=int(service.code),
                    user_id=service.id,
                    username=service.username,
                    panel=panels.get(int(service.in_panel or 0)),
                    panel_code=service.in_panel,
                    package_size=service.package_size,
                    expiration_time=service.expiration_time,
                    enable=bool(service.enable),
                    expired=bool(service.expiration_time and service.expiration_time <= now),
                    is_test=bool(service.is_test),
                )
                for service in rows
            ],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelServicesResponse, handle)


@router.post("/panel/services/toggle", response_model=ActionResponse)
async def toggle_service(payload: PanelServiceToggleRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.set_service_enabled(actor, payload.code, payload.enabled)
        if not ok:
            return ActionResponse(ok=False, error="سرویسی با این کد پیدا نشد.")
        return ActionResponse(message="سرویس فعال شد." if payload.enabled else "سرویس غیرفعال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/services/delete", response_model=ActionResponse)
async def delete_service(payload: PanelServiceDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_service_row(actor, payload.code)
        if not ok:
            return ActionResponse(ok=False, error="سرویسی با این کد پیدا نشد.")
        return ActionResponse(message="سرویس از دیتابیس ربات حذف شد (روی پنل حذف نشد).")

    return await guard.run(payload, request, ActionResponse, handle)

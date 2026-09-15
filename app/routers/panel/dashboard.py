"""Dashboard overview and the caller's own identity."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.models.panel.common import PanelRequest
from app.models.panel.dashboard import (
    PanelDashboardResponse,
    PanelDayPoint,
    PanelMeResponse,
    PanelStats,
)
from app.panel import queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


@router.post("/panel/me", response_model=PanelMeResponse)
async def panel_me(payload: PanelRequest, request: Request) -> PanelMeResponse:
    """Confirm the caller is an admin and return what the shell needs."""

    async def handle(actor: PanelActor) -> PanelMeResponse:
        badges = await queries.sidebar_badges()
        return PanelMeResponse(user_id=actor.user_id, username=actor.username, badges=badges)

    return await guard.run(payload, request, PanelMeResponse, handle)


@router.post("/panel/dashboard", response_model=PanelDashboardResponse)
async def panel_dashboard(payload: PanelRequest, request: Request) -> PanelDashboardResponse:
    async def handle(_: PanelActor) -> PanelDashboardResponse:
        stats, series, badges = await asyncio.gather(
            queries.dashboard_stats(),
            queries.daily_series(14),
            queries.sidebar_badges(),
        )
        return PanelDashboardResponse(
            stats=PanelStats(**stats),
            series=[PanelDayPoint(**point) for point in series],
            badges=badges,
        )

    return await guard.run(payload, request, PanelDashboardResponse, handle)

"""Sale plans: volume, duration and price per panel."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.models.panel.common import ActionResponse
from app.models.panel.plans import (
    PLAN_TYPES,
    RESET_STRATEGIES,
    PanelPlanDeleteRequest,
    PanelPlanRow,
    PanelPlanSaveRequest,
    PanelPlansRequest,
    PanelPlansResponse,
)
from app.models.panel.services import PanelPanelOption
from app.panel import mutations, queries
from app.panel.forms import parse_icon, parse_style
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


@router.post("/panel/plans", response_model=PanelPlansResponse)
async def list_plans(payload: PanelPlansRequest, request: Request) -> PanelPlansResponse:
    async def handle(_: PanelActor) -> PanelPlansResponse:
        plans, panels = await asyncio.gather(
            queries.list_plans(payload.panel.strip()),
            queries.panel_names(),
        )
        return PanelPlansResponse(
            plans=[
                PanelPlanRow(
                    id=int(plan.id),
                    panel_code=int(plan.panel_code),
                    panel=panels.get(int(plan.panel_code)),
                    storage=float(plan.storage or 0),
                    duration=int(plan.duration or 0),
                    price=float(plan.price or 0),
                    plan_type=plan.plan_type,
                    data_limit_reset_strategy=plan.data_limit_reset_strategy,
                    ip_limit=int(plan.ip_limit or 0),
                    display_button_text=plan.display_button_text,
                    button_style=plan.button_style,
                    button_icon=plan.button_icon,
                )
                for plan in plans
            ],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
        )

    return await guard.run(payload, request, PanelPlansResponse, handle)


@router.post("/panel/plans/save", response_model=ActionResponse)
async def save_plan(payload: PanelPlanSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        panels = await queries.panel_names()
        if payload.panel_code not in panels:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        try:
            icon = parse_icon(payload.button_icon)
        except ValueError:
            return ActionResponse(ok=False, error="آیدی ایموجی معتبر نیست.")

        values = {
            "panel_code": payload.panel_code,
            "storage": payload.storage,
            "duration": payload.duration,
            "price": payload.price,
            "plan_type": payload.plan_type if payload.plan_type in PLAN_TYPES else "volume",
            "data_limit_reset_strategy": (
                payload.data_limit_reset_strategy
                if payload.data_limit_reset_strategy in RESET_STRATEGIES
                else "no_reset"
            ),
            "ip_limit": payload.ip_limit,
            "display_button_text": payload.display_button_text.strip() or None,
            "button_style": parse_style(payload.button_style),
            "button_icon": icon,
        }

        if payload.plan_id is not None and await queries.get_plan(payload.plan_id) is None:
            return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")

        await mutations.upsert_plan(actor, payload.plan_id, values)
        return ActionResponse(message="پلن ذخیره شد." if payload.plan_id else "پلن اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/plans/delete", response_model=ActionResponse)
async def delete_plan(payload: PanelPlanDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_plan(actor, payload.plan_id)
        if not ok:
            return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")
        return ActionResponse(message="پلن حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

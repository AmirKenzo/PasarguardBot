"""Reseller accounts, their usage caps and billing history, plus reseller plans."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request

from app.db.models.reseller_plans import PRICING_MODES
from app.models.panel.common import ActionResponse, PanelRequest, page_meta
from app.models.panel.resellers import (
    RESELLER_STATUSES,
    PanelResellerDeleteRequest,
    PanelResellerDetailRequest,
    PanelResellerDetailResponse,
    PanelResellerPlanDeleteRequest,
    PanelResellerPlanRow,
    PanelResellerPlanSaveRequest,
    PanelResellerPlansResponse,
    PanelResellerRow,
    PanelResellerSnapshotRow,
    PanelResellersRequest,
    PanelResellersResponse,
    PanelResellerUpdateRequest,
)
from app.models.panel.services import PanelPanelOption
from app.panel import mutations, queries
from app.panel.forms import parse_icon, parse_style
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()

GB = 1024**3


def _reseller_row(account, panels: dict[int, str]) -> PanelResellerRow:
    return PanelResellerRow(
        code=int(account.code),
        telegram_id=account.telegram_id,
        username=account.username,
        panel_code=account.panel_code,
        panel=panels.get(int(account.panel_code or 0)),
        pricing_mode=account.pricing_mode,
        purchased_volume=account.purchased_volume,
        usage_cap_bytes=account.usage_cap_bytes,
        max_users=account.max_users,
        createtime=account.createtime,
        expiration_time=account.expiration_time,
        status=account.status,
    )


@router.post("/panel/resellers", response_model=PanelResellersResponse)
async def list_resellers(payload: PanelResellersRequest, request: Request) -> PanelResellersResponse:
    async def handle(_: PanelActor) -> PanelResellersResponse:
        (rows, total), panels = await asyncio.gather(
            queries.list_resellers(
                status=payload.status,
                q=payload.q.strip(),
                page=payload.page,
                per_page=payload.limit,
            ),
            queries.panel_names(),
        )
        return PanelResellersResponse(
            resellers=[_reseller_row(account, panels) for account in rows],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelResellersResponse, handle)


@router.post("/panel/resellers/detail", response_model=PanelResellerDetailResponse)
async def reseller_detail(payload: PanelResellerDetailRequest, request: Request) -> PanelResellerDetailResponse:
    async def handle(_: PanelActor) -> PanelResellerDetailResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return PanelResellerDetailResponse(ok=False, error="حساب نمایندگی با این کد پیدا نشد.")
        snapshots, panels = await asyncio.gather(
            queries.reseller_snapshots(payload.code),
            queries.panel_names(),
        )
        return PanelResellerDetailResponse(
            reseller=_reseller_row(account, panels),
            snapshots=[
                PanelResellerSnapshotRow(
                    id=int(snapshot.id),
                    used_traffic=int(snapshot.used_traffic or 0),
                    billed_amount=int(snapshot.billed_amount or 0),
                    snapshot_at=snapshot.snapshot_at,
                )
                for snapshot in snapshots
            ],
        )

    return await guard.run(payload, request, PanelResellerDetailResponse, handle)


@router.post("/panel/resellers/update", response_model=ActionResponse)
async def update_reseller(payload: PanelResellerUpdateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error="حساب نمایندگی با این کد پیدا نشد.")

        values: dict = {
            "usage_cap_bytes": int(payload.usage_cap_gb * GB) if payload.usage_cap_gb else None,
            "max_users": payload.max_users,
        }
        if payload.status in RESELLER_STATUSES:
            values["status"] = payload.status
        if payload.extend_days:
            base = max(int(account.expiration_time or 0), int(time.time()))
            values["expiration_time"] = base + payload.extend_days * 86400

        ok = await mutations.update_reseller(actor, payload.code, values)
        if not ok:
            return ActionResponse(ok=False, error="تغییری ثبت نشد.")
        return ActionResponse(message="حساب نمایندگی به‌روزرسانی شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/delete", response_model=ActionResponse)
async def delete_reseller(payload: PanelResellerDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_reseller(actor, payload.code)
        if not ok:
            return ActionResponse(ok=False, error="حساب نمایندگی با این کد پیدا نشد.")
        return ActionResponse(message="حساب نمایندگی حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


# --------------------------------------------------------------------------- #
#  Reseller plans                                                               #
# --------------------------------------------------------------------------- #


@router.post("/panel/reseller-plans", response_model=PanelResellerPlansResponse)
async def list_reseller_plans(payload: PanelRequest, request: Request) -> PanelResellerPlansResponse:
    async def handle(_: PanelActor) -> PanelResellerPlansResponse:
        plans, panels = await asyncio.gather(
            queries.list_reseller_plans(),
            queries.panel_names(),
        )
        return PanelResellerPlansResponse(
            plans=[
                PanelResellerPlanRow(
                    id=int(plan.id),
                    panel_code=int(plan.panel_code),
                    panel=panels.get(int(plan.panel_code)),
                    pricing_mode=plan.pricing_mode,
                    price=float(plan.price or 0),
                    unit_price=float(plan.unit_price or 0),
                    min_volume=float(plan.min_volume or 0),
                    max_volume=float(plan.max_volume or 0),
                    volume_step=float(plan.volume_step or 1),
                    max_users=int(plan.max_users or 0),
                    duration=int(plan.duration or 0),
                    role_id=int(plan.role_id or 0),
                    role_name=plan.role_name,
                    enable=bool(plan.enable),
                    display_button_text=plan.display_button_text,
                    button_style=plan.button_style,
                    button_icon=plan.button_icon,
                )
                for plan in plans
            ],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
            pricing_modes=list(PRICING_MODES),
        )

    return await guard.run(payload, request, PanelResellerPlansResponse, handle)


@router.post("/panel/reseller-plans/save", response_model=ActionResponse)
async def save_reseller_plan(payload: PanelResellerPlanSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        panels = await queries.panel_names()
        if payload.panel_code not in panels:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        if payload.pricing_mode not in PRICING_MODES:
            return ActionResponse(ok=False, error="مدل قیمت‌گذاری معتبر نیست.")
        if payload.max_volume and payload.max_volume < payload.min_volume:
            return ActionResponse(ok=False, error="حداکثر حجم نمی‌تواند از حداقل کمتر باشد.")
        try:
            icon = parse_icon(payload.button_icon)
        except ValueError:
            return ActionResponse(ok=False, error="آیدی ایموجی معتبر نیست.")

        values = {
            "panel_code": payload.panel_code,
            "pricing_mode": payload.pricing_mode,
            "price": payload.price,
            "unit_price": payload.unit_price,
            "min_volume": payload.min_volume,
            "max_volume": payload.max_volume,
            "volume_step": payload.volume_step,
            "max_users": payload.max_users,
            "duration": payload.duration,
            "role_id": payload.role_id,
            "role_name": payload.role_name.strip() or None,
            "enable": payload.enable,
            "display_button_text": payload.display_button_text.strip() or None,
            "button_style": parse_style(payload.button_style),
            "button_icon": icon,
        }

        if payload.plan_id is not None and await queries.get_reseller_plan(payload.plan_id) is None:
            return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")

        await mutations.upsert_reseller_plan(actor, payload.plan_id, values)
        return ActionResponse(message="پلن نمایندگی ذخیره شد." if payload.plan_id else "پلن نمایندگی اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/reseller-plans/delete", response_model=ActionResponse)
async def delete_reseller_plan(payload: PanelResellerPlanDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_reseller_plan(actor, payload.plan_id)
        if not ok:
            return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")
        return ActionResponse(message="پلن نمایندگی حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

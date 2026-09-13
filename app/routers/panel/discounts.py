"""Discount codes: list, create, edit, delete."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.marketing import (
    PanelDiscountDeleteRequest,
    PanelDiscountRow,
    PanelDiscountSaveRequest,
    PanelDiscountsRequest,
    PanelDiscountsResponse,
)
from app.panel import mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


@router.post("/panel/discounts", response_model=PanelDiscountsResponse)
async def list_discounts(payload: PanelDiscountsRequest, request: Request) -> PanelDiscountsResponse:
    async def handle(_: PanelActor) -> PanelDiscountsResponse:
        rows, total = await queries.list_discounts(page=payload.page, per_page=payload.limit)
        now = int(time.time())
        return PanelDiscountsResponse(
            discounts=[
                PanelDiscountRow(
                    id=int(item.id),
                    code=item.code,
                    discount_percentage=int(item.discount_percentage or 0),
                    usage_limit=int(item.usage_limit or 0),
                    times_used=int(item.times_used or 0),
                    expiration_date=item.expiration_date,
                    user_id=item.user_id,
                    is_public=bool(item.is_public),
                    expired=bool(item.expiration_date and item.expiration_date <= now),
                    exhausted=bool(item.usage_limit and (item.times_used or 0) >= item.usage_limit),
                )
                for item in rows
            ],
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelDiscountsResponse, handle)


@router.post("/panel/discounts/save", response_model=ActionResponse)
async def save_discount(payload: PanelDiscountSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        values = {
            "code": payload.code.strip(),
            "discount_percentage": payload.discount_percentage,
            "usage_limit": payload.usage_limit,
            "expiration_date": (int(time.time()) + payload.expires_days * 86400 if payload.expires_days else None),
            "user_id": payload.user_id,
            "is_public": payload.is_public,
        }

        if payload.code_id is not None:
            if await queries.get_discount(payload.code_id) is None:
                return ActionResponse(ok=False, error="کدی با این شناسه پیدا نشد.")
            clash = await queries.get_discount_by_code(values["code"])
            if clash is not None and int(clash.id) != payload.code_id:
                return ActionResponse(ok=False, error="این کد تخفیف قبلاً ثبت شده است.")

        saved = await mutations.upsert_discount(actor, payload.code_id, values)
        if saved is None:
            return ActionResponse(ok=False, error="این کد تخفیف قبلاً ثبت شده است.")
        return ActionResponse(message="کد تخفیف ذخیره شد." if payload.code_id else "کد تخفیف ساخته شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/discounts/delete", response_model=ActionResponse)
async def delete_discount(payload: PanelDiscountDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_discount(actor, payload.code_id)
        if not ok:
            return ActionResponse(ok=False, error="کدی با این شناسه پیدا نشد.")
        return ActionResponse(message="کد تخفیف حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

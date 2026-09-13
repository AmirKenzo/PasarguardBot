"""Manual card transactions: list, approve, reject."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.services import (
    PanelTransactionActionRequest,
    PanelTransactionRow,
    PanelTransactionsRequest,
    PanelTransactionsResponse,
)
from app.panel import mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


@router.post("/panel/transactions", response_model=PanelTransactionsResponse)
async def list_transactions(payload: PanelTransactionsRequest, request: Request) -> PanelTransactionsResponse:
    async def handle(_: PanelActor) -> PanelTransactionsResponse:
        (rows, total), badges = await asyncio.gather(
            queries.list_transactions(
                status=payload.status,
                method=payload.method,
                page=payload.page,
                per_page=payload.limit,
            ),
            queries.sidebar_badges(),
        )
        return PanelTransactionsResponse(
            transactions=[
                PanelTransactionRow(
                    id=int(tx.id),
                    user_id=tx.user_id,
                    amount=int(tx.amount or 0),
                    status=tx.status,
                    method=getattr(tx, "method", None),
                    created_at=tx.created_at,
                    receipt=getattr(tx, "receipt", None),
                )
                for tx in rows
            ],
            meta=page_meta(total, payload.page, payload.limit),
            pending_total=int(badges.get("transactions", 0)),
        )

    return await guard.run(payload, request, PanelTransactionsResponse, handle)


@router.post("/panel/transactions/approve", response_model=ActionResponse)
async def approve_transaction(payload: PanelTransactionActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.approve_transaction(actor, payload.tx_id)
        if not ok:
            return ActionResponse(ok=False, error="این تراکنش پیدا نشد یا قبلاً رسیدگی شده است.")
        return ActionResponse(message="تراکنش تأیید و موجودی کاربر شارژ شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/transactions/reject", response_model=ActionResponse)
async def reject_transaction(payload: PanelTransactionActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.reject_transaction(actor, payload.tx_id)
        if not ok:
            return ActionResponse(ok=False, error="این تراکنش پیدا نشد یا قبلاً رسیدگی شده است.")
        return ActionResponse(message="تراکنش رد شد.")

    return await guard.run(payload, request, ActionResponse, handle)

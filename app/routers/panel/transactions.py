"""Transactions across every payment method: list, approve, reject, and the
same review actions the bot's own manual-card log-channel buttons offer."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.services import (
    PanelReceiptLinkRequest,
    PanelReceiptLinkResponse,
    PanelTransactionActionRequest,
    PanelTransactionRow,
    PanelTransactionsRequest,
    PanelTransactionsResponse,
    PanelTransactionStats,
)
from app.panel import mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.utils.security.receipt_links import consume_receipt_token, create_receipt_token
from config import ADMIN_ID

router = APIRouter()

_NO_STORE_HEADERS = {"Cache-Control": "no-store, private"}


@router.post("/panel/transactions", response_model=PanelTransactionsResponse)
async def list_transactions(payload: PanelTransactionsRequest, request: Request) -> PanelTransactionsResponse:
    async def handle(_: PanelActor) -> PanelTransactionsResponse:
        (rows, total), badges, stats = await asyncio.gather(
            queries.list_unified_transactions(
                tx_id=payload.tx_id,
                user_id=payload.user_id,
                amount=payload.amount,
                method=payload.method,
                status=payload.status,
                days=payload.days,
                page=payload.page,
                per_page=payload.limit,
            ),
            queries.sidebar_badges(),
            queries.transaction_stats(),
        )
        return PanelTransactionsResponse(
            transactions=[
                PanelTransactionRow(
                    id=row.raw_id,
                    source=row.source,
                    method=row.method,
                    user_id=row.user_id,
                    amount=int(row.amount or 0),
                    status=row.status,
                    created_at=row.created_at,
                    has_receipt=row.source == "tx" and row.method == "manual_card",
                )
                for row in rows
            ],
            meta=page_meta(total, payload.page, payload.limit),
            pending_total=int(badges.get("transactions", 0)),
            stats=PanelTransactionStats(**stats),
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


@router.post("/panel/transactions/request-fix", response_model=ActionResponse)
async def request_fix(payload: PanelTransactionActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.request_receipt_fix_transaction(actor, payload.tx_id)
        if not ok:
            return ActionResponse(ok=False, error="این تراکنش پیدا نشد یا قبلاً رسیدگی شده است.")
        return ActionResponse(message="درخواست اصلاح مبلغ برای کاربر ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/transactions/report-mismatch", response_model=ActionResponse)
async def report_mismatch(payload: PanelTransactionActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.report_card_mismatch_transaction(actor, payload.tx_id)
        if not ok:
            return ActionResponse(ok=False, error="این تراکنش پیدا نشد یا قبلاً رسیدگی شده است.")
        return ActionResponse(message="پیام عدم تطابق کارت برای کاربر ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/transactions/receipt-link", response_model=PanelReceiptLinkResponse)
async def receipt_link(payload: PanelReceiptLinkRequest, request: Request) -> PanelReceiptLinkResponse:
    async def handle(actor: PanelActor) -> PanelReceiptLinkResponse:
        tx = await queries.get_transaction(payload.tx_id)
        if tx is None or not tx.message_id or not tx.message_chat_id:
            return PanelReceiptLinkResponse(ok=False, error="رسیدی برای این تراکنش ثبت نشده است.")
        token = create_receipt_token(actor.user_id, payload.tx_id)
        return PanelReceiptLinkResponse(url=f"/api/panel/transactions/receipt/{token}")

    return await guard.run(payload, request, PanelReceiptLinkResponse, handle)


@router.get("/panel/transactions/receipt/{token}")
async def stream_receipt(token: str) -> Response:
    """Stream a receipt photo straight from Telegram — never downloaded to disk.

    A plain <img> can't carry the panel's usual auth, so this is gated by the
    single-use link minted from ``/panel/transactions/receipt-link`` instead.
    """
    ok, error, admin_id, tx_id = consume_receipt_token(token)
    if not ok or admin_id not in ADMIN_ID:
        return Response(content=error or "این لینک معتبر نیست.", status_code=403, headers=_NO_STORE_HEADERS)

    tx = await queries.get_transaction(tx_id)
    if tx is None or not tx.message_id or not tx.message_chat_id:
        return Response(content="رسید پیدا نشد.", status_code=404, headers=_NO_STORE_HEADERS)

    from app import Kenzo

    message = await Kenzo.get_messages(int(tx.message_chat_id), ids=int(tx.message_id))
    if message is None or not message.media:
        return Response(content="رسید پیدا نشد.", status_code=404, headers=_NO_STORE_HEADERS)

    async def chunks():
        async for chunk in Kenzo.iter_download(message.media):
            yield chunk

    return StreamingResponse(chunks(), media_type="image/jpeg", headers=_NO_STORE_HEADERS)

"""TonPays payment webhook.

Only the X-API-Key header is checked here (TonPays does not document its signature scheme);
the body is used just to find the invoice, whose real status is then re-read from TonPays.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request

from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.models.router_models import WebhookResponse
from app.services.payments.tonpays import refresh_by_invoice_id, verify_webhook_key

logger = get_logger(__name__)

router = APIRouter()


def _log_failure(task: asyncio.Task) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("TonPays webhook processing failed: %s", exc, exc_info=exc)


@router.post("/payments/tonpays/callback", response_model=WebhookResponse)
async def tonpays_callback(request: Request) -> WebhookResponse:
    settings = await SettingsManager().get_settings()
    if not verify_webhook_key(request.headers.get("x-api-key"), settings):
        raise HTTPException(status_code=403, detail="Invalid API key")
    try:
        payload = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None
    invoice_id = str(payload.get("invoice_id") or "").strip() if isinstance(payload, dict) else ""
    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoice_id missing")
    logger.info(
        "TonPays webhook: invoice=%s event=%s delivery=%s",
        invoice_id,
        request.headers.get("x-tonpays-event"),
        request.headers.get("x-tonpays-delivery-id"),
    )
    task = asyncio.create_task(refresh_by_invoice_id(invoice_id), name="tonpays_webhook")
    task.add_done_callback(_log_failure)
    return WebhookResponse(ok=True, message="received")

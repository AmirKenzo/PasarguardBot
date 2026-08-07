"""
Webhook router for handling Marzban events.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.logger import get_logger
from app.models.router_models import WebhookResponse
from app.routers.webhook.processor import process_webhook_events
from app.utils.security.secrets_cache import get_webhook_secret

logger = get_logger(__name__)

webhook_router = APIRouter()


def _log_background_webhook_failure(task: asyncio.Task) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("Background webhook processing failed: %s", exc, exc_info=exc)


@webhook_router.post("/webhook", response_model=WebhookResponse)
async def handle_webhook(request: Request) -> WebhookResponse:
    """Handle incoming webhook events from Marzban."""

    try:
        debug = logger.isEnabledFor(logging.DEBUG)
        if debug:
            logger.debug("📥 WEBHOOK REQUEST RECEIVED")
            logger.debug("\n📋 HEADERS:")
            for header_name, header_value in request.headers.items():
                logger.debug("  %s: %s", header_name, header_value)

        # Check webhook secret
        signature = request.headers.get("x-webhook-secret")
        if not signature:
            logger.info("\n❌ ERROR: Signature header missing")
            raise HTTPException(status_code=403, detail="Signature header missing")

        if debug:
            logger.debug("\n🔐 Received header secret (masked)")

        if signature != get_webhook_secret():
            logger.info("❌ ERROR: Invalid shared secret")
            raise HTTPException(status_code=403, detail="Invalid shared secret")

        if debug:
            logger.debug("✅ Webhook secret validated")

        # Read raw body
        body = await request.body()
        if debug:
            logger.debug("\n📦 RAW BODY (bytes): %s bytes", len(body))
            preview = body.hex()[:100]
            logger.debug("📦 RAW BODY (hex): %s%s", preview, "..." if len(body) > 50 else "")

        # Parse JSON payload
        try:
            payload = json.loads(body)
            if debug:
                logger.debug("\n📄 PARSED JSON:")
                logger.debug("%s", json.dumps(payload, indent=2, ensure_ascii=False))
        except json.JSONDecodeError as e:
            logger.info(f"\n❌ ERROR: Invalid JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

        # Handle list or single event
        if isinstance(payload, list):
            if debug:
                logger.debug("\n📊 Processing %s events:", len(payload))
            events = payload
        else:
            logger.info("\n📊 Processing single event:")
            events = [payload]

        # Ack immediately; process off the HTTP request path.
        task = asyncio.create_task(process_webhook_events(events), name="webhook_process")
        task.add_done_callback(_log_background_webhook_failure)

        if debug:
            logger.debug("\n✅ Webhook accepted for background processing")

        return WebhookResponse(ok=True, message="Webhook received successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"\n❌ ERROR: Failed to process webhook: {e}")
        logger.debug(f"Failed to process webhook: {e}", exc_info=True)
        return WebhookResponse(ok=False, message=f"Error processing webhook: {e!s}")


logger.debug("Webhook router loaded successfully")

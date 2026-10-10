"""
Webhook router for handling Marzban events.
"""

import asyncio
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.logger import get_logger
from app.models.router_models import WebhookResponse
from app.routers.webhook.ir_gateways import router as ir_gateways_router
from app.routers.webhook.processor import process_webhook_events
from app.routers.webhook.tonpays import router as tonpays_router
from app.utils.security.secrets_cache import get_webhook_secret

logger = get_logger(__name__)

webhook_router = APIRouter()
webhook_router.include_router(tonpays_router)
webhook_router.include_router(ir_gateways_router)


# Credentials that must never reach the logs, even at DEBUG level.
_REDACTED_HEADERS = frozenset({"x-webhook-secret", "authorization", "cookie", "x-api-key"})


def _is_valid_secret(received: str | None, expected: str | None) -> bool:
    """Constant-time comparison so response timing does not leak the secret."""
    if not received or not expected:
        return False
    return hmac.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))


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
                shown = "***" if header_name.lower() in _REDACTED_HEADERS else header_value
                logger.debug("  %s: %s", header_name, shown)

        # Check webhook secret
        signature = request.headers.get("x-webhook-secret")
        if not signature:
            logger.info("\n❌ ERROR: Signature header missing")
            raise HTTPException(status_code=403, detail="Signature header missing")

        if debug:
            logger.debug("\n🔐 Received header secret (masked)")

        if not _is_valid_secret(signature, get_webhook_secret()):
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

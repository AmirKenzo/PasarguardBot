"""
Webhook router for handling Marzban events.
"""

import json

from fastapi import APIRouter, HTTPException, Request

from app.logger import get_logger
from app.models.router_models import WebhookResponse
from app.routers.webhook.processor import process_webhook_events
from app.utils.security.secrets_cache import get_webhook_secret

logger = get_logger(__name__)

webhook_router = APIRouter()


@webhook_router.post("/webhook", response_model=WebhookResponse)
async def handle_webhook(request: Request) -> WebhookResponse:
    """Handle incoming webhook events from Marzban."""

    try:
        # Log all headers
        logger.debug("📥 WEBHOOK REQUEST RECEIVED")
        logger.debug("\n📋 HEADERS:")
        for header_name, header_value in request.headers.items():
            logger.debug(f"  {header_name}: {header_value}")

        # Check webhook secret
        signature = request.headers.get("x-webhook-secret")
        if not signature:
            logger.info("\n❌ ERROR: Signature header missing")
            raise HTTPException(status_code=403, detail="Signature header missing")

        logger.debug("\n🔐 Received webhook secret header")

        if signature != get_webhook_secret():
            logger.info("❌ ERROR: Invalid shared secret")
            raise HTTPException(status_code=403, detail="Invalid shared secret")

        logger.debug("✅ Webhook secret validated")

        # Read raw body
        body = await request.body()
        logger.debug(f"\n📦 RAW BODY (bytes): {len(body)} bytes")
        logger.debug(
            f"📦 RAW BODY (hex): {body.hex()[:100]}..." if len(body) > 50 else f"📦 RAW BODY (hex): {body.hex()}"
        )

        # Parse JSON payload
        try:
            payload = json.loads(body)
            logger.debug("\n📄 PARSED JSON:")
            logger.debug(json.dumps(payload, indent=2, ensure_ascii=False))
        except json.JSONDecodeError as e:
            logger.info(f"\n❌ ERROR: Invalid JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

        # Handle list or single event
        if isinstance(payload, list):
            logger.debug(f"\n📊 Processing {len(payload)} events:")
            events = payload
        else:
            logger.info("\n📊 Processing single event:")
            events = [payload]

        # Process events using webhook service
        await process_webhook_events(events)

        logger.debug("\n✅ Webhook processed successfully")

        return WebhookResponse(ok=True, message="Webhook received successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"\n❌ ERROR: Failed to process webhook: {e}")
        logger.debug(f"Failed to process webhook: {e}", exc_info=True)
        return WebhookResponse(ok=False, message=f"Error processing webhook: {e!s}")


logger.debug("Webhook router loaded successfully")

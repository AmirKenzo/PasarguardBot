"""ForApp SMS webhook: ``POST /api/payments/forapp/webhook``.

The Android ForApp app POSTs bank deposit SMS here. Auth via one of:
``X-API-Key`` header, ``Authorization: Bearer <key>`` or ``?key=<key>``.
"""

from __future__ import annotations

import json
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.logger import get_logger
from app.models.router_models import WebhookResponse
from app.services.payments.forapp import get_forapp_api_keys, is_valid_forapp_key
from app.services.payments.forapp_match import process_forapp_deposit

logger = get_logger(__name__)

router = APIRouter()

# In-memory sliding-window rate limiter (per client IP). ForApp sends at most
# a few SMS per minute; anything beyond that is a misconfiguration or abuse.
_RATE_LIMIT_MAX = 30
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_rate_hits: dict[str, deque[float]] = {}


def _is_rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    hits = _rate_hits.get(client_ip)
    if hits is None:
        hits = _rate_hits[client_ip] = deque()
    while hits and now - hits[0] > _RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _RATE_LIMIT_MAX:
        return True
    hits.append(now)
    # Bound memory: drop idle client entries opportunistically.
    if len(_rate_hits) > 1024:
        for key in [k for k, v in _rate_hits.items() if not v]:
            del _rate_hits[key]
    return False


def _allowed_keys() -> list[str]:
    try:
        from config import FORAPP_API_KEY, FORAPP_API_KEYS

        env = {"FORAPP_API_KEYS": FORAPP_API_KEYS, "FORAPP_API_KEY": FORAPP_API_KEY}
    except Exception:
        env = None
    return get_forapp_api_keys(env)


def _provided_key(request: Request) -> str | None:
    header_key = request.headers.get("x-api-key")
    if header_key and header_key.strip():
        return header_key.strip()
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    for param in ("key", "api_key", "api-key", "token"):
        value = request.query_params.get(param)
        if value and value.strip():
            return value.strip()
    return None


@router.get("/payments/forapp/health")
async def forapp_health() -> JSONResponse:
    configured = bool(_allowed_keys())
    return JSONResponse({"ok": True, "configured": configured})


@router.post("/payments/forapp/webhook", response_model=WebhookResponse)
async def forapp_webhook(request: Request) -> WebhookResponse:
    allowed = _allowed_keys()
    if not allowed:
        raise HTTPException(status_code=503, detail="ForApp webhook not configured")
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    if not is_valid_forapp_key(_provided_key(request), allowed):
        raise HTTPException(status_code=403, detail="Invalid API key")
    try:
        payload = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    # Process synchronously, not fire-and-forget: the phone only retries when
    # it gets no 2xx, so a 200 must mean the SMS is safely stored. The path is
    # one upsert plus indexed lookups — milliseconds at SMS rates. A crash
    # mid-processing yields no 2xx, the phone retries, and the idempotent
    # ledger dedupes the replay.
    result = await process_forapp_deposit(payload, fallback_id=request.headers.get("idempotency-key"))
    return WebhookResponse(ok=True, message=result["status"])


@router.post("/webhook/forapp", include_in_schema=False)
async def forapp_webhook_legacy_alias(request: Request) -> WebhookResponse:
    """Alias for the pre-release URL from the early draft guide.

    The canonical path is ``/api/payments/forapp/webhook``; this exists so a
    destination configured with the old ``/api/webhook/forapp`` path keeps
    working instead of failing with 405.
    """
    return await forapp_webhook(request)

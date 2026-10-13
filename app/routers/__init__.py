"""
Router initialization and FastAPI app setup.
"""

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.routers.webapp.errors import SESSION_INVALID
from app.routers.webapp.state import rejected_session, verified_session_tokens, webapp_auth_headers
from app.utils.security import maybe_renew_session_token
from app.version import VERSIONS
from config import API_DOCS_ENABLED

from .panel import panel_router
from .webapp import serve_webapp, webapp_router
from .webhook import webhook_router

# Create FastAPI application
api_app = FastAPI(
    title="PasarguardBot API",
    version=VERSIONS.app,
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


# Routes whose handlers read credentials from the auth ContextVar.
AUTH_HEADER_PREFIXES = ("/api/webapp", "/api/panel")
SESSION_CODE_PREFIX = "/api/webapp"


async def _tag_session_invalid(response: Response) -> Response:
    """Add ``error_code: session_invalid`` to an ``ok: false`` JSON body, keeping status and headers."""
    if not (response.headers.get("content-type") or "").startswith("application/json"):
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
    try:
        data = json.loads(body)
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("ok") is False and not data.get("error_code"):
        data["error_code"] = SESSION_INVALID
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tagged = Response(content=body, status_code=response.status_code)
    tagged.raw_headers = [(k, v) for k, v in response.raw_headers if k.lower() != b"content-length"]
    tagged.raw_headers.append((b"content-length", str(len(body)).encode("latin-1")))
    return tagged


class WebAppAuthHeaderMiddleware(BaseHTTPMiddleware):
    """Promote session/init auth from headers into a request ContextVar.

    Preferred transport (avoids query-string leakage in logs/referrers):
      Authorization: Bearer <session_token>
      X-Session-Token: <session_token>
      X-Telegram-Init-Data: <telegram_init_data>
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith(AUTH_HEADER_PREFIXES):
            session = request.headers.get("x-session-token") or _extract_bearer(request.headers.get("authorization"))
            init_data = request.headers.get("x-telegram-init-data")
            token = webapp_auth_headers.set((session or None, init_data or None))
            verified: set[str] = set()
            verified_token = verified_session_tokens.set(verified)
            rejected: list[bool] = []
            rejected_token = rejected_session.set(rejected)
            try:
                response = await call_next(request)
            finally:
                rejected_session.reset(rejected_token)
                verified_session_tokens.reset(verified_token)
                webapp_auth_headers.reset(token)
            if rejected and path.startswith(SESSION_CODE_PREFIX):
                response = await _tag_session_invalid(response)
            if session and session in verified:
                renewed = maybe_renew_session_token(session)
                if renewed:
                    response.headers["X-Session-Token"] = renewed
            return response
        return await call_next(request)


api_app.add_middleware(WebAppAuthHeaderMiddleware)

api_app.include_router(webhook_router, prefix="/api", tags=["Webhook"])
api_app.include_router(webapp_router, prefix="/api", tags=["WebApp"])
api_app.include_router(panel_router, prefix="/api", tags=["AdminPanel"])

# Serve built frontend assets
frontend_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
assets_dir = frontend_dist_dir / "assets"

if assets_dir.exists():
    # Primary mount used by Vite base '/webapp/'
    api_app.mount("/webapp/assets", StaticFiles(directory=str(assets_dir)), name="webapp-assets")
    # Secondary mount to support reverse proxies that only forward under /api/*
    api_app.mount("/api/webapp/assets", StaticFiles(directory=str(assets_dir)), name="webapp-assets-api")

api_app.get("/", response_class=HTMLResponse)(serve_webapp)
api_app.get("/{full_path:path}", response_class=HTMLResponse)(serve_webapp)

__all__ = ["api_app"]

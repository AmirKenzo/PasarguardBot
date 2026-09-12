"""
Router initialization and FastAPI app setup.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.routers.webapp.state import webapp_auth_headers
from app.version import VERSIONS

from .webapp import webapp_router
from .webhook import webhook_router

# Create FastAPI application
api_app = FastAPI(
    title="PasarguardBot API",
    version=VERSIONS.app,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


class WebAppAuthHeaderMiddleware(BaseHTTPMiddleware):
    """Promote session/init auth from headers into a request ContextVar.

    Preferred transport (avoids query-string leakage in logs/referrers):
      Authorization: Bearer <session_token>
      X-Session-Token: <session_token>
      X-Telegram-Init-Data: <telegram_init_data>
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path.startswith("/api/webapp"):
            session = request.headers.get("x-session-token") or _extract_bearer(request.headers.get("authorization"))
            init_data = request.headers.get("x-telegram-init-data")
            token = webapp_auth_headers.set((session or None, init_data or None))
            try:
                return await call_next(request)
            finally:
                webapp_auth_headers.reset(token)
        return await call_next(request)


api_app.add_middleware(WebAppAuthHeaderMiddleware)

api_app.include_router(webhook_router, prefix="/api", tags=["Webhook"])
api_app.include_router(webapp_router, prefix="/api", tags=["WebApp"])

# Serve built frontend assets
frontend_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
assets_dir = frontend_dist_dir / "assets"

if assets_dir.exists():
    # Primary mount used by Vite base '/webapp/'
    api_app.mount("/webapp/assets", StaticFiles(directory=str(assets_dir)), name="webapp-assets")
    # Secondary mount to support reverse proxies that only forward under /api/*
    api_app.mount("/api/webapp/assets", StaticFiles(directory=str(assets_dir)), name="webapp-assets-api")

__all__ = ["api_app"]

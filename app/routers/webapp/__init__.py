"""
WebApp router package for handling Telegram WebApp endpoints and browser login.

Split by feature so new endpoints can be added in their own small module
instead of growing one large file:
  - auth: login, OTP, session, logout, web-account management
  - services: service list/detail, config links, clients, link/sub change
  - usage_chart: per-service usage chart
  - renew: manual renewal options + confirm
  - buy: new purchase flow (delegates to WebAppPurchaseService)
  - balance: balance top-up methods and deposit flows
  - transactions: unified payment transaction history
  - upgrade: extend-time / extra-volume purchases and config transfer
  - state: shared in-memory auth state (OTP sessions, revoked tokens, locks)
"""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.logger import get_logger
from app.routers.webapp.auth import router as auth_router
from app.routers.webapp.balance import router as balance_router
from app.routers.webapp.buy import router as buy_router
from app.routers.webapp.pwa import router as pwa_router
from app.routers.webapp.renew import router as renew_router
from app.routers.webapp.services import router as services_router
from app.routers.webapp.transactions import router as transactions_router
from app.routers.webapp.upgrade import router as upgrade_router
from app.routers.webapp.usage_chart import router as usage_chart_router

logger = get_logger(__name__)
webapp_router = APIRouter()

# Serve built frontend (standard multi-file build)
frontend_dist_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"


webapp_router.include_router(auth_router)
webapp_router.include_router(services_router)
webapp_router.include_router(usage_chart_router)
webapp_router.include_router(renew_router)
webapp_router.include_router(buy_router)
webapp_router.include_router(balance_router)
webapp_router.include_router(transactions_router)
webapp_router.include_router(upgrade_router)
webapp_router.include_router(pwa_router)


@webapp_router.get("/webapp", response_class=HTMLResponse)
@webapp_router.get("/webapp/{full_path:path}", response_class=HTMLResponse)
async def serve_webapp(_: Request, full_path: str = "") -> Response:
    """Serve a build file verbatim (service worker, its precache chunk, ...),
    or fall back to the app shell for any client-side route (SPA fallback)."""
    if full_path:
        candidate = (frontend_dist_dir / full_path).resolve()
        if candidate.is_file() and frontend_dist_dir.resolve() in candidate.parents:
            media_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            return FileResponse(candidate, media_type=media_type)
    return FileResponse(frontend_dist_dir / "index.html", media_type="text/html; charset=utf-8")


logger.debug("WebApp router loaded successfully")

__all__ = ["serve_webapp", "webapp_router"]

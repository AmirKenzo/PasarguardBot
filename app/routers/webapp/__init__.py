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
  - state: shared in-memory auth state (OTP sessions, revoked tokens, locks)
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.logger import get_logger
from app.routers.webapp.auth import router as auth_router
from app.routers.webapp.balance import router as balance_router
from app.routers.webapp.buy import router as buy_router
from app.routers.webapp.renew import router as renew_router
from app.routers.webapp.services import router as services_router
from app.routers.webapp.transactions import router as transactions_router
from app.routers.webapp.usage_chart import router as usage_chart_router

logger = get_logger(__name__)
webapp_router = APIRouter()

# Serve built frontend (standard multi-file build)
frontend_dist_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"


@webapp_router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp(_: Request) -> FileResponse:
    """Serve the main web app HTML file."""
    return FileResponse(frontend_dist_dir / "index.html", media_type="text/html; charset=utf-8")


webapp_router.include_router(auth_router)
webapp_router.include_router(services_router)
webapp_router.include_router(usage_chart_router)
webapp_router.include_router(renew_router)
webapp_router.include_router(buy_router)
webapp_router.include_router(balance_router)
webapp_router.include_router(transactions_router)

logger.debug("WebApp router loaded successfully")

__all__ = ["webapp_router"]

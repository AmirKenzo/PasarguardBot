"""Admin panel API.

Mounted under ``/api/panel``. Every endpoint goes through
:func:`app.routers.panel.guard.run`, which authenticates the caller with the
existing WebApp login and requires that the user is listed in ``ADMIN_ID``.

Split by feature, mirroring ``app/routers/webapp``:
  - auth: admin resolution shared by every endpoint
  - guard: the wrapper that authenticates and normalises errors
  - dashboard: overview counters, revenue series, caller identity
  - users: bot users, balance, block, direct message
  - services: sold services
  - transactions: manual card payments, approve/reject
  - payments: crypto wallets, manual cards, auto-approve rules
  - panels: connected PasarGuard panels
  - plans: sale plans per panel
  - resellers: reseller accounts, billing history and reseller plans
  - discounts: discount codes
  - referral: referral settings and reward history
  - broadcast: bulk message jobs
  - channels: join-lock channels and log destinations
  - texts: the editable bot texts
  - keyboard: home menu layout, button labels, colours and icons
  - settings: the bot settings form
  - reports: sales and customer reports
  - tools: system status, backups, bulk volume/time increase
  - audit: the panel activity log
"""

from fastapi import APIRouter

from app.logger import get_logger
from app.routers.panel.audit import router as audit_router
from app.routers.panel.broadcast import router as broadcast_router
from app.routers.panel.channels import router as channels_router
from app.routers.panel.dashboard import router as dashboard_router
from app.routers.panel.discounts import router as discounts_router
from app.routers.panel.keyboard import router as keyboard_router
from app.routers.panel.panels import router as panels_router
from app.routers.panel.payments import router as payments_router
from app.routers.panel.plans import router as plans_router
from app.routers.panel.referral import router as referral_router
from app.routers.panel.reports import router as reports_router
from app.routers.panel.resellers import router as resellers_router
from app.routers.panel.services import router as services_router
from app.routers.panel.settings import router as settings_router
from app.routers.panel.texts import router as texts_router
from app.routers.panel.tools import router as tools_router
from app.routers.panel.transactions import router as transactions_router
from app.routers.panel.users import router as users_router

logger = get_logger(__name__)

panel_router = APIRouter()
panel_router.include_router(dashboard_router)
panel_router.include_router(users_router)
panel_router.include_router(services_router)
panel_router.include_router(transactions_router)
panel_router.include_router(payments_router)
panel_router.include_router(panels_router)
panel_router.include_router(plans_router)
panel_router.include_router(resellers_router)
panel_router.include_router(discounts_router)
panel_router.include_router(referral_router)
panel_router.include_router(broadcast_router)
panel_router.include_router(channels_router)
panel_router.include_router(texts_router)
panel_router.include_router(keyboard_router)
panel_router.include_router(settings_router)
panel_router.include_router(reports_router)
panel_router.include_router(tools_router)
panel_router.include_router(audit_router)

logger.debug("Admin panel router loaded successfully")

__all__ = ["panel_router"]

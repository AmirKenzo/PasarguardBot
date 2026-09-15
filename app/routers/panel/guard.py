"""One wrapper that turns a handler body into an authenticated panel endpoint.

Keeps every feature module free of repeated auth and error plumbing, and makes
it impossible to add a route that forgets the admin check.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request

from app.logger import get_logger
from app.models.panel.common import PanelRequest
from app.routers.panel.auth import PanelActor, PanelAuthError, authenticate_admin

log = get_logger(__name__)


async def run[ResponseT](
    payload: PanelRequest,
    request: Request | None,
    response_model: type[ResponseT],
    handler: Callable[[PanelActor], Awaitable[ResponseT]],
) -> ResponseT:
    """Authenticate, run ``handler``, and turn any failure into ``ok=False``."""
    try:
        actor = await authenticate_admin(
            init_data=payload.init_data,
            session_token=payload.session_token,
            request=request,
        )
    except PanelAuthError as exc:
        return response_model(ok=False, error=exc.message)

    try:
        return await handler(actor)
    except Exception as exc:
        log.error("panel: %s failed for admin %s: %s", response_model.__name__, actor.user_id, exc, exc_info=True)
        return response_model(ok=False, error="اجرای این عملیات با خطا روبه‌رو شد.")

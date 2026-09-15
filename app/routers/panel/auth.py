"""Admin authentication for the web panel.

The panel reuses the WebApp login (phone OTP or Telegram init data) instead of
keeping its own accounts, then checks that the authenticated user is listed in
``ADMIN_ID``. Nothing about an admin is stored: the only panel table is the
audit log.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.logger import get_logger
from app.routers.webapp.auth import authenticate_user
from config import ADMIN_ID

log = get_logger(__name__)


class PanelAuthError(Exception):
    """Raised when the caller is not a signed-in admin."""

    def __init__(self, message: str, *, forbidden: bool = False):
        super().__init__(message)
        self.message = message
        self.forbidden = forbidden


@dataclass(slots=True)
class PanelActor:
    """Who is making the current request."""

    user_id: int
    ip: str

    @property
    def username(self) -> str:
        return str(self.user_id)


def client_ip(request: Request | None) -> str:
    """Best-effort caller IP, used only for the audit trail."""
    if request is None:
        return ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    client = getattr(request, "client", None)
    return (getattr(client, "host", "") or "")[:64]


async def authenticate_admin(
    *,
    init_data: str | None = None,
    session_token: str | None = None,
    request: Request | None = None,
) -> PanelActor:
    """Resolve the caller and require that they are an admin.

    Raises :class:`PanelAuthError` — never returns a non-admin.
    """
    try:
        user_id = await authenticate_user(init_data=init_data, session_token=session_token)
    except ValueError as exc:
        raise PanelAuthError(str(exc) or "ورود لازم است") from exc

    if user_id is None:
        raise PanelAuthError("ورود لازم است")

    if int(user_id) not in ADMIN_ID:
        log.warning("panel: non-admin %s tried to reach the panel API", user_id)
        raise PanelAuthError("این حساب دسترسی مدیریت ندارد.", forbidden=True)

    return PanelActor(user_id=int(user_id), ip=client_ip(request))

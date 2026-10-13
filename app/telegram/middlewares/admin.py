"""Admin context — admins skip restrictive middlewares via ``applies()`` checks."""

from __future__ import annotations

from app.telegram.middlewares.base import BaseMiddleware
from app.telegram.middlewares.context import MiddlewareContext


class AdminContextMiddleware(BaseMiddleware):
    """Ensures ``ctx.is_admin`` is set (already on context; documents intent in pipeline)."""

    name = "admin_context"
    priority = 10

    async def before(self, ctx: MiddlewareContext) -> None:
        ctx.extras["is_admin"] = ctx.is_admin

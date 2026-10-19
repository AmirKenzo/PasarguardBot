"""Central middleware registry and pipeline executor."""

from __future__ import annotations

from app.logger import get_logger
from app.telegram.middlewares.base import BaseMiddleware, StopPipeline
from app.telegram.middlewares.context import MiddlewareContext

logger = get_logger(__name__)


class MiddlewareManager:
    def __init__(self) -> None:
        self._pipelines: dict[str, list[BaseMiddleware]] = {}

    def register(self, pipeline: str, middleware: BaseMiddleware) -> None:
        chain = self._pipelines.setdefault(pipeline, [])
        if any(m.name == middleware.name for m in chain):
            logger.debug("Middleware %s already in pipeline %s", middleware.name, pipeline)
            return
        chain.append(middleware)
        chain.sort(key=lambda m: m.priority)

    def register_many(self, pipeline: str, middlewares: list[BaseMiddleware]) -> None:
        for mw in middlewares:
            self.register(pipeline, mw)

    def get_chain(self, pipeline: str) -> list[BaseMiddleware]:
        return list(self._pipelines.get(pipeline, []))

    async def run_before(self, ctx: MiddlewareContext, pipeline: str) -> None:
        for middleware in self.get_chain(pipeline):
            if not middleware.applies(ctx):
                continue
            try:
                await middleware.before(ctx)
            except StopPipeline:
                raise
            except Exception:
                logger.exception(
                    "Middleware %s failed in pipeline %s (user=%s)",
                    middleware.name,
                    pipeline,
                    ctx.user_id,
                )

    async def run_after(
        self,
        ctx: MiddlewareContext,
        pipeline: str,
        handler_result: object = None,
    ) -> None:
        for middleware in reversed(self.get_chain(pipeline)):
            if not middleware.applies(ctx):
                continue
            try:
                await middleware.after(ctx, handler_result)
            except Exception:
                logger.exception(
                    "Middleware %s after-hook failed in pipeline %s",
                    middleware.name,
                    pipeline,
                )


# Global singleton used by Telethon bridge and decorators
middleware_manager = MiddlewareManager()

PIPELINE_NEWMESSAGE = "newmessage_global"
PIPELINE_CALLBACK = "callback_global"

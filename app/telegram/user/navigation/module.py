"""Package entry point for shared user navigation callbacks."""

from app.telegram.plugins import PluginContext
from app.telegram.user.navigation import callbacks

MODULE_NAME = "user.navigation"
MODULE_DESCRIPTION = "Shared user navigation callbacks (cancel-to-home, no-op buttons)"


def setup(ctx: PluginContext) -> None:
    callbacks.register(ctx)

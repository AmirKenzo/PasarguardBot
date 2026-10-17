"""Package entry point for admin stats/info bot."""

from app.telegram.admin.info_bot import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.info_bot"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin stats and info bot panel"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

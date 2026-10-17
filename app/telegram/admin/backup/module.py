"""Package entry point for the admin backup module."""

from app.telegram.admin.backup import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.backup"
MODULE_DESCRIPTION = "Admin database/.env backup flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

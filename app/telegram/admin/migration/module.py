"""Package entry point for the admin migration module."""

from app.telegram.admin.migration import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.migration"
MODULE_DESCRIPTION = "Admin bot-to-bot data migration wizard"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

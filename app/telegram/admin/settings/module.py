"""Package entry point for the admin settings module."""

from app.telegram.admin.settings import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.settings"
MODULE_DESCRIPTION = "Admin settings flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

"""Package entry point for the admin support module."""

from app.telegram.admin.support import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.support"
MODULE_DESCRIPTION = "Admin support reply flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

"""Package entry point for admin log management."""

from app.telegram.admin.logs import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.logs"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin log destination management"

def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

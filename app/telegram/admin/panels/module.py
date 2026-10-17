"""Package entry point for admin panel management flow."""

from app.telegram.admin.panels import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.panels"
MODULE_DESCRIPTION = "admin panel management flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

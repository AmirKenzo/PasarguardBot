"""Package entry point for admin discount code management."""

from app.telegram.admin.discounts import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.discounts"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin discount code management"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

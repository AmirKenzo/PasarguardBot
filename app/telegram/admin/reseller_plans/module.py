"""Package entry point for admin reseller plans module."""

from app.telegram.admin.reseller_plans import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.reseller_plans"
MODULE_ORDER = 1010
MODULE_DESCRIPTION = "Admin reseller plan management"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

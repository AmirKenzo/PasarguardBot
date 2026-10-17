"""Package entry point for user reseller purchase flow."""

from app.telegram.plugins import PluginContext
from app.telegram.user.reseller import callbacks, messages

MODULE_NAME = "user.reseller"
MODULE_REQUIRED = True
MODULE_ORDER = 1010
MODULE_DESCRIPTION = "user reseller purchase and account management"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

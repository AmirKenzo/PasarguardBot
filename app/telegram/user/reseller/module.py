"""Package entry point for user reseller purchase flow."""

from app.telegram.plugins import PluginContext
from app.telegram.user.reseller import bot_reseller, callbacks, messages

MODULE_NAME = "user.reseller"
MODULE_REQUIRED = True
MODULE_ORDER = 1010
MODULE_DESCRIPTION = "user reseller purchase and account management"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)
    bot_reseller.register(kenzo)

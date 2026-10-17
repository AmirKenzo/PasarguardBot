"""Package entry point for the user balance module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.balance import callbacks, ir_gateways, messages, tonpays

MODULE_NAME = "user.balance"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User balance and payment flow"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)
    tonpays.register(kenzo)
    ir_gateways.register(kenzo)

"""Package entry point for the user balance module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.balance import callbacks, ir_gateways, messages, tonpays

MODULE_NAME = "user.balance"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User balance and payment flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)
    tonpays.register(ctx)
    ir_gateways.register(ctx)

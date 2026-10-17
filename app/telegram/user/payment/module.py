"""Package entry point for the user payment module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.payment import callbacks

MODULE_NAME = "user.payment"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Telegram Stars payment flow"


def setup(ctx: PluginContext) -> None:
    callbacks.register(ctx)

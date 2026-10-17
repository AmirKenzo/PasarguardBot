"""Package entry point for the admin wallets module."""

from app.telegram.admin.wallets import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.wallets"
MODULE_DESCRIPTION = "Admin wallet flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

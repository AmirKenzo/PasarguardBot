"""Package entry point for the user help module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.help import callbacks, messages

MODULE_NAME = "user.help"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User help menu and app download callbacks"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

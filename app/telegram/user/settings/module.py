"""Package entry point for the user settings module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.settings import callbacks, messages

MODULE_NAME = "user.settings"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User advanced display settings"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

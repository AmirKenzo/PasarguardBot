"""Package entry point for the user profile module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.profile import callbacks, messages

MODULE_NAME = "user.profile"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User profile flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

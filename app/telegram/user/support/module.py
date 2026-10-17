"""Package entry point for the user support module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.support import messages

MODULE_NAME = "user.support"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User support messaging flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

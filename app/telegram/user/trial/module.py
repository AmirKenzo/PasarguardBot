"""Package entry point for the user trial module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.trial import messages

MODULE_NAME = "user.trial"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User free trial flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

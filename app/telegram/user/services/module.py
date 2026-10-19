"""Package entry point for user service management flow."""

from app.telegram.plugins import PluginContext
from app.telegram.user.services import callbacks, messages

MODULE_NAME = "user.services"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "user service management flow"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)

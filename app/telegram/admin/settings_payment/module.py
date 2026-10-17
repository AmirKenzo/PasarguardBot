"""Package entry point for the admin settings_payment module."""

from app.telegram.admin.settings_payment import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.settings_payment"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin payment settings flow"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)

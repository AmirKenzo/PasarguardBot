"""Package entry point for the admin send2all module."""

from app.telegram.admin.send2all import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.send2all"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin broadcast flow"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)

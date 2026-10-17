"""Package entry point for the admin channel_lock module."""

from app.telegram.admin.channel_lock import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.channel_lock"
MODULE_DESCRIPTION = "Admin channel lock flow"


def setup(kenzo: PluginContext) -> None:
    messages.register(kenzo)
    callbacks.register(kenzo)

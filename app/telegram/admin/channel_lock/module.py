"""Package entry point for the admin channel_lock module."""

from app.telegram.admin.channel_lock import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.channel_lock"
MODULE_DESCRIPTION = "Admin channel lock flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

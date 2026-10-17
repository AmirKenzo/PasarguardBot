"""Package entry point for the admin home panel module."""

from app.telegram.admin.admin_home import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.admin_home"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin home panel shell"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

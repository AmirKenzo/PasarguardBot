"""Package entry point for admin manage_user."""

from app.telegram.admin.manage_user import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.manage_user"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin user management flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

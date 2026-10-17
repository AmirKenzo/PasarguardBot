"""Package entry point for the admin ping module."""

from app.telegram.admin.ping import messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.ping"
MODULE_ORDER = 10
MODULE_DESCRIPTION = "Admin ping command"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

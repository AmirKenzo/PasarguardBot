"""Package entry point for the user mini-app module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.miniapp import messages

MODULE_NAME = "user.miniapp"
MODULE_DESCRIPTION = "Mini app entry button"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

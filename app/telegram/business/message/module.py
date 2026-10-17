"""Package entry point for the slim business message module."""

from app.telegram.business.message import messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "business.message"
MODULE_DESCRIPTION = "Telegram Business admin commands (id/add/remove/info/ip)"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

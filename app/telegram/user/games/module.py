"""Package entry point for user games."""

from app.telegram.plugins import PluginContext
from app.telegram.user.games import callbacks, messages

MODULE_NAME = "user.games"
MODULE_DESCRIPTION = "User games and rewards"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

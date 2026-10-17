"""Package entry point for the admin TonPays settings module."""

from app.telegram.admin.tonpays import handlers
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.tonpays"
MODULE_DESCRIPTION = "Admin TonPays gateway settings"


def setup(ctx: PluginContext) -> None:
    handlers.register(ctx)

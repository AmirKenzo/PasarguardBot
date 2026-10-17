"""Package entry point for the admin Iranian gateways settings module."""

from app.telegram.admin.ir_gateways import handlers
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.ir_gateways"
MODULE_DESCRIPTION = "Admin Iranian direct gateway settings"


def setup(ctx: PluginContext) -> None:
    handlers.register(ctx)

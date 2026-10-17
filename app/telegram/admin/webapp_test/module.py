"""Package entry point for the admin webapp test module."""

from app.telegram.admin.webapp_test import messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.webapp_test"
MODULE_ORDER = 10
MODULE_DESCRIPTION = "Admin command to open the WebApp for testing"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)

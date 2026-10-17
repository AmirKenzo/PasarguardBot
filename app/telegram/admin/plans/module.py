"""Package entry point for the admin plans module."""

from app.telegram.admin.plans import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.plans"
MODULE_DESCRIPTION = "Admin plan management flow"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

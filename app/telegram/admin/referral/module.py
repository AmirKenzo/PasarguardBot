"""Package entry point for admin referral system management."""

from app.telegram.admin.referral import callbacks, messages
from app.telegram.plugins import PluginContext

MODULE_NAME = "admin.referral"
MODULE_DESCRIPTION = "Admin referral system management"


def setup(ctx: PluginContext) -> None:
    messages.register(ctx)
    callbacks.register(ctx)

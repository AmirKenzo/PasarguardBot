"""Package entry point for the user referral earnings module."""

from app.telegram.plugins import PluginContext
from app.telegram.user.referral_earnings import handlers

MODULE_NAME = "user.referral_earnings"
MODULE_REQUIRED = True
MODULE_ORDER = 990
MODULE_DESCRIPTION = "Referral earnings: withdrawal and wallet transfer"


def setup(ctx: PluginContext) -> None:
    handlers.register(ctx)

"""Package entry point for the user referral earnings module."""

from app.telegram.user.referral_earnings import handlers

MODULE_NAME = "user.referral_earnings"
MODULE_ENABLED = True
MODULE_ORDER = 990
MODULE_DESCRIPTION = "Referral earnings: withdrawal and wallet transfer"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    handlers.register(client)
    _registered_clients.add(client_id)

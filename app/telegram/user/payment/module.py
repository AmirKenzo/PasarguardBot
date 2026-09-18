"""Package entry point for the user payment module."""

from app.telegram.user.payment import callbacks

MODULE_NAME = "user.payment"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Telegram Stars payment flow"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    callbacks.register(client)
    _registered_clients.add(client_id)

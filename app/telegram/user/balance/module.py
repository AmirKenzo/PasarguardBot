"""Package entry point for the user balance module."""

from app.telegram.user.balance import callbacks, messages, tonpays, zarinpal

MODULE_NAME = "user.balance"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "User balance and payment flow"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    callbacks.register(client)
    tonpays.register(client)
    zarinpal.register(client)
    _registered_clients.add(client_id)

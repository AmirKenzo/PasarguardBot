"""Package entry point for admin referral system management."""

from app.telegram.admin.referral import callbacks, messages

MODULE_NAME = "admin.referral"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Admin referral system management"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    callbacks.register(client)
    _registered_clients.add(client_id)

"""Package entry point for the admin migration module."""

from app.telegram.admin.migration import callbacks, messages

MODULE_NAME = "admin.migration"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Admin bot-to-bot data migration wizard"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    callbacks.register(client)
    _registered_clients.add(client_id)

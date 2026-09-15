"""Package entry point for the in-chat home menu module."""

from app.telegram.user.menu import messages

MODULE_NAME = "user.menu"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "In-chat home menu callbacks"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    _registered_clients.add(client_id)

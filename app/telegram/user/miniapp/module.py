"""Package entry point for the user mini-app module."""

from app.telegram.user.miniapp import messages

MODULE_NAME = "user.miniapp"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Mini app entry button"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    _registered_clients.add(client_id)

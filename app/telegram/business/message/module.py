"""Package entry point for the slim business message module."""

from app.telegram.business.message import messages

MODULE_NAME = "business.message"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Telegram Business admin commands (id/add/remove/info/ip)"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    _registered_clients.add(client_id)

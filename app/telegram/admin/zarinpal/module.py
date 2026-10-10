"""Package entry point for the admin Zarinpal settings module."""

from app.telegram.admin.zarinpal import handlers

MODULE_NAME = "admin.zarinpal"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Admin Zarinpal gateway settings"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    handlers.register(client)
    _registered_clients.add(client_id)

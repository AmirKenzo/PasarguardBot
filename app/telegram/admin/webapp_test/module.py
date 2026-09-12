"""Package entry point for the admin webapp test module."""

from app.telegram.admin.webapp_test import messages

MODULE_NAME = "admin.webapp_test"
MODULE_ENABLED = True
MODULE_ORDER = 10
MODULE_DESCRIPTION = "Admin command to open the WebApp for testing"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    _registered_clients.add(client_id)

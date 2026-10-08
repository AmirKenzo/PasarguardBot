"""Package entry point for the user start module.

Routing ownership:
  /start (except buy/free/charge deep links) → this module
  Check_join                                   → this module
  /start buy, /buy, menu buy                   → user/shop
  /start free, menu trial                      → user/trial
  /start charge, /charge, menu balance         → user/balance
  /help, menu help                             → user/help
  menu advanced settings                       → user/settings
  /myaccount, menu my services                 → user/services
  menu profile                                 → user/profile
  menu support                                 → user/support
  global channel lock (callbacks + messages)   → middlewares/channel_join.py
"""

from app.telegram.user.start import callbacks, home_inline, messages

MODULE_NAME = "user.start"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "User start and home navigation"

_registered_clients: set[int] = set()


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    callbacks.register(client)
    home_inline.register(client)
    _registered_clients.add(client_id)

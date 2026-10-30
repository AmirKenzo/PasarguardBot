"""Every bot reseller module imports cleanly."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "app.db.crud.bot_reseller",
        "app.services.bot_reseller.core",
        "app.jobs.reseller.bot_billing",
        "app.routers.panel.bot_resellers",
        "app.routers.webapp.bot_reseller",
        "app.telegram.user.reseller.bot_reseller",
        "app.telegram.user.reseller.module",
        "app.telegram.keyboards.home",
        "app.panel.queries",
        "app.jobs.registry",
    ],
)
def test_imports(module: str) -> None:
    importlib.import_module(module)

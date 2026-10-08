"""FastAPI's interactive docs and schema are not served unless explicitly enabled."""

from __future__ import annotations

import pytest

import app.routers as routers_module


@pytest.mark.skipif(routers_module.API_DOCS_ENABLED, reason="API docs enabled in this environment")
def test_docs_routes_are_disabled_by_default() -> None:
    app = routers_module.api_app
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    paths = {getattr(route, "path", None) for route in app.routes}
    assert not paths & {"/docs", "/redoc", "/openapi.json"}

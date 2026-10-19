"""Admin panel users endpoints."""

from __future__ import annotations

import pytest

from app.models.panel.common import PanelRequest
from app.routers.panel import guard, users
from app.routers.panel.auth import PanelActor


@pytest.fixture(autouse=True)
def admin(monkeypatch):
    async def authenticate(**kwargs):
        return PanelActor(user_id=1, ip="127.0.0.1")

    monkeypatch.setattr(guard, "authenticate_admin", authenticate)


async def test_users_stats_returns_query_values(monkeypatch):
    values = {
        "new_24h": 5,
        "new_prev_24h": 3,
        "new_7d": 20,
        "new_daily": [1, 2, 3, 4, 2, 3, 5],
        "new_buyers_24h": 2,
        "active": 90,
        "total": 100,
    }

    async def users_stats():
        return values

    monkeypatch.setattr(users.queries, "users_stats", users_stats)
    result = await users.users_stats(PanelRequest(), None)
    assert result.ok
    assert result.model_dump(include=set(values)) == values

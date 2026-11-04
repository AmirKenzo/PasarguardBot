from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.crud.bot_reseller import UsageResult
from app.services.bot_reseller import core


@pytest.mark.parametrize("operation", ["reset", "delete"])
@pytest.mark.parametrize("accepted", [False, True])
async def test_guarded_settlement_controls_destructive_panel_calls(monkeypatch, operation, accepted):
    reseller = SimpleNamespace(id=1, telegram_id=42, status="active")
    user = SimpleNamespace(
        id=7, reseller_id=1, deleted_at=None, panel_code=2, panel_user_id=8, baseline_bytes=100, observation_revision=0
    )
    ctx = core.ResellerContext(reseller, [], {})
    apply = AsyncMock(return_value=UsageResult(ok=accepted))
    update = AsyncMock(return_value=True)
    crud = SimpleNamespace(get_user=AsyncMock(return_value=user), apply_usage=apply, update_user=update)
    monkeypatch.setattr(core, "BotResellerCRUD", lambda: crud)
    monkeypatch.setattr(core, "prices_for", AsyncMock(return_value={1: 2800}))
    monkeypatch.setattr(core, "_panel", AsyncMock(return_value=object()))
    monkeypatch.setattr(core.panel_api, "get_user", AsyncMock(return_value=object()))
    monkeypatch.setattr(core.panel_api, "traffic_counter", lambda user: 150)
    reset, remove = AsyncMock(), AsyncMock()
    monkeypatch.setattr(core.panel_api, "reset_usage", reset)
    monkeypatch.setattr(core.panel_api, "remove_user", remove)
    call = core.reset_user_usage(ctx, 7) if operation == "reset" else core.delete_user(ctx, 7)
    if accepted:
        await call
    else:
        with pytest.raises(core.Refused):
            await call
    apply.assert_awaited_once_with(1, {7: 150}, {1: 2800}, expected_observations={7: (100, 0)})
    assert reset.await_count == int(accepted and operation == "reset")
    assert remove.await_count == int(accepted and operation == "delete")
    assert update.await_count == int(accepted and operation == "delete")

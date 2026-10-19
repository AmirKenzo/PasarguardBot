"""A receipt that cannot be hashed is accepted, logged and kept out of auto-approval."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest

from app.db.crud import manual_auto_approve_rules
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.receipt_hash import compute_receipt_phash


def test_unreadable_image_returns_none_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert compute_receipt_phash(b"not an image") is None
    assert any("duplicate check skipped" in record.getMessage() for record in caplog.records)


def test_manual_only_never_schedules_auto_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def get_settings(self):
        calls.append("settings")
        return SimpleNamespace(manual_auto_confirm=True)

    monkeypatch.setattr(manual_auto_approve_rules.SettingsManager, "get_settings", get_settings)
    tx = SimpleNamespace(id=1, user_id=5, auto_approve_at=None)

    rule = asyncio.run(ManualAutoApproveRuleCRUD().schedule_for_transaction(tx, manual_only=True))

    assert rule is None
    assert tx.auto_approve_at is None
    assert calls == []

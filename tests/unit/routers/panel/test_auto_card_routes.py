"""Admin panel auto card-to-card tab: overview, save validation and webhook key rotation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.panel.common import PanelRequest
from app.models.panel.payments import PanelAutoCardSaveRequest
from app.routers.panel import guard, payments
from app.routers.panel.auth import PanelActor
from app.utils.security.secrets_cache import SECRET_SMS_WEBHOOK, _cache


def _settings(**fields) -> SimpleNamespace:
    base = {
        "id": 1,
        "auto_cart": True,
        "auto_card_visibility": None,
        "cart_num": "6037991234567890",
        "cart_name": "Ali",
        "auto_deposit_min": 50_000,
        "auto_deposit_max": 2_000_000,
        "auto_bonus_enabled": False,
        "auto_bonus_percent": 0,
    }
    base.update(fields)
    return SimpleNamespace(**base)


@pytest.fixture
def audit_log(monkeypatch) -> list[dict]:
    records: list[dict] = []

    async def authenticate(**kwargs):
        return PanelActor(user_id=111111111, ip="127.0.0.1")

    async def record(**kwargs):
        records.append(kwargs)

    monkeypatch.setattr(guard, "authenticate_admin", authenticate)
    monkeypatch.setattr(payments.audit, "record", record)
    return records


@pytest.fixture
def settings_store(monkeypatch) -> dict:
    store: dict = {"settings": _settings(), "updates": []}

    class _Settings:
        async def get_settings(self):
            return store["settings"]

        async def update_setting(self, setting_id, **fields):
            store["updates"].append(fields)

    monkeypatch.setattr(payments, "SettingsManager", _Settings)
    return store


async def test_overview_returns_settings_key_and_today_numbers(monkeypatch, audit_log, settings_store) -> None:
    class _AutoCard:
        async def count_pending(self) -> int:
            return 2

    class _Transactions:
        async def get_breakdown(self, start_ts: int) -> dict:
            return {"auto_approved_count": 4, "auto_approved_sum": 900_000}

    monkeypatch.setattr(payments, "CRUDAutoCard", _AutoCard)
    monkeypatch.setattr(payments, "TransactionCRUD", _Transactions)
    monkeypatch.setattr(payments, "sms_webhook_url", lambda: "https://bot.example/api/sms")
    monkeypatch.setitem(_cache, SECRET_SMS_WEBHOOK, "k" * 64)

    result = await payments.auto_card_overview(PanelRequest(), None)

    assert result.ok
    assert result.visibility == "safe_mode"
    assert (result.card_number, result.card_name) == ("6037991234567890", "Ali")
    assert result.webhook_url == "https://bot.example/api/sms"
    assert result.api_key == "k" * 64
    assert (result.stats.pending_invoices, result.stats.approved_today, result.stats.amount_today) == (2, 4, 900_000)


async def test_save_rejects_inverted_range(audit_log, settings_store) -> None:
    payload = PanelAutoCardSaveRequest(deposit_min=500_000, deposit_max=100_000)

    result = await payments.auto_card_save(payload, None)

    assert not result.ok
    assert settings_store["updates"] == []


async def test_save_maps_fields_to_settings(audit_log, settings_store) -> None:
    payload = PanelAutoCardSaveRequest(
        enabled=False, visibility="all", card_number=" 1234 ", card_name="", deposit_min=10_000, deposit_max=90_000
    )

    result = await payments.auto_card_save(payload, None)

    assert result.ok
    assert settings_store["updates"] == [
        {
            "auto_deposit_min": 10_000,
            "auto_deposit_max": 90_000,
            "auto_cart": False,
            "auto_card_visibility": "all",
            "cart_num": "1234",
            "cart_name": None,
        }
    ]
    assert [entry["action"] for entry in audit_log] == ["auto_card_settings_update"]


async def test_rotate_key_records_audit(monkeypatch, audit_log) -> None:
    rotated: list[str] = []

    class _Secrets:
        async def rotate(self, name: str) -> str:
            rotated.append(name)
            return "new"

    monkeypatch.setattr(payments, "SecretsCRUD", _Secrets)

    result = await payments.auto_card_rotate_key(PanelRequest(), None)

    assert result.ok
    assert rotated == [SECRET_SMS_WEBHOOK]
    assert [entry["action"] for entry in audit_log] == ["sms_webhook_rotate"]

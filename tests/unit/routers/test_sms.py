from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db.crud.auto_card import AutoCardPaymentResult
from app.routers import sms as sms_module
from app.routers.sms import sms_router
from app.utils.security.secrets_cache import SECRET_SMS_WEBHOOK, _cache

_SECRET = "s3cr3t-sms-key-0123456789"


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(sms_router, prefix="/api")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
def process_mock():
    with patch.object(sms_module, "process_payment_sms", new=AsyncMock()) as mock:
        yield mock


def _set_secret(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setitem(_cache, SECRET_SMS_WEBHOOK, value)


class TestSmsWebhookAuth:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("configured", ["", "ak", "short-secret"])
    async def test_unconfigured_or_weak_secret_rejects_everything(self, client, process_mock, monkeypatch, configured):
        _set_secret(monkeypatch, configured)
        response = await client.post(
            "/api/sms",
            json={"text": "deposit", "key": configured},
            headers={"x-api-key": configured},
        )
        assert response.status_code == 401
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wrong_key_is_rejected(self, client, process_mock, monkeypatch):
        _set_secret(monkeypatch, _SECRET)
        response = await client.post("/api/sms", json={"text": "deposit"}, headers={"x-api-key": "wrong"})
        assert response.status_code == 401
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_key_is_rejected(self, client, process_mock, monkeypatch):
        _set_secret(monkeypatch, _SECRET)
        response = await client.post("/api/sms", json={"text": "deposit"})
        assert response.status_code == 401
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("headers", "body_key"),
        [
            ({"x-api-key": _SECRET}, None),
            ({"authorization": f"Bearer {_SECRET}"}, None),
            ({}, _SECRET),
        ],
    )
    async def test_valid_key_is_accepted(self, client, process_mock, monkeypatch, headers, body_key):
        _set_secret(monkeypatch, _SECRET)
        body = {"text": "deposit"}
        if body_key:
            body["key"] = body_key
        response = await client.post("/api/sms", json=body, headers=headers)
        assert response.json() == {"status": "success"}
        process_mock.assert_awaited_once_with("deposit", fallback_amount_rial=None, is_deposit=None)


class _FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys.add(key)
        return True

    async def delete(self, key):
        self.keys.discard(key)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()

    async def _get_redis():
        return redis

    monkeypatch.setattr(sms_module, "get_redis", _get_redis)
    return redis


_FORAPP_BODY = {
    "id": "6f1c2a9e-1111-4222-8333-944455556666",
    "test": False,
    "sender": "+989000000000",
    "bank": "Mellat",
    "body": "deposit 1,000,123",
    "amount": 1000123,
    "code": "123",
    "unit": "rial",
    "is_deposit": True,
}


class TestForAppWebhook:
    @pytest.mark.asyncio
    async def test_default_forapp_payload_is_processed(self, client, process_mock, monkeypatch, fake_redis):
        _set_secret(monkeypatch, _SECRET)
        response = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
        assert response.json() == {"status": "success"}
        process_mock.assert_awaited_once_with("deposit 1,000,123", fallback_amount_rial=1_000_123, is_deposit=True)

    @pytest.mark.asyncio
    async def test_test_message_is_not_processed(self, client, process_mock, monkeypatch, fake_redis):
        _set_secret(monkeypatch, _SECRET)
        body = {**_FORAPP_BODY, "id": "test-abc", "test": True}
        response = await client.post("/api/sms", json=body, headers={"X-API-Key": _SECRET})
        assert response.json() == {"status": "ignored", "reason": "test"}
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_repeated_delivery_is_processed_once(self, client, process_mock, monkeypatch, fake_redis):
        _set_secret(monkeypatch, _SECRET)
        headers = {"X-API-Key": _SECRET}
        first = await client.post("/api/sms", json=_FORAPP_BODY, headers=headers)
        second = await client.post("/api/sms", json=_FORAPP_BODY, headers=headers)
        assert first.json() == {"status": "success"}
        assert second.json() == {"status": "ignored", "reason": "duplicate"}
        process_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_delivery_can_be_retried(self, client, monkeypatch, fake_redis):
        _set_secret(monkeypatch, _SECRET)
        failing = AsyncMock(side_effect=[RuntimeError("db down"), None])
        monkeypatch.setattr(sms_module, "process_payment_sms", failing)
        headers = {"X-API-Key": _SECRET}
        first = await client.post("/api/sms", json=_FORAPP_BODY, headers=headers)
        second = await client.post("/api/sms", json=_FORAPP_BODY, headers=headers)
        assert first.status_code == 500
        assert second.json() == {"status": "success"}
        assert failing.await_count == 2

    @pytest.mark.asyncio
    async def test_idempotency_header_is_used_without_body_id(self, client, process_mock, monkeypatch, fake_redis):
        _set_secret(monkeypatch, _SECRET)
        headers = {"X-API-Key": _SECRET, "Idempotency-Key": "abc-1"}
        await client.post("/api/sms", json={"text": "deposit"}, headers=headers)
        second = await client.post("/api/sms", json={"text": "deposit"}, headers=headers)
        assert second.json() == {"status": "ignored", "reason": "duplicate"}
        process_mock.assert_awaited_once()


def _patch_auto_card(monkeypatch: pytest.MonkeyPatch, claimed: list[int]) -> AsyncMock:
    processed = AsyncMock()

    class _AutoCard:
        async def approve_and_credit(self, amount, *, bonus_enabled, bonus_percent):
            claimed.append(amount)
            return AutoCardPaymentResult(
                invoice=SimpleNamespace(code=321, id=5, first_amount=100_000), balance=110_000, bonus=10_000
            )

    monkeypatch.setattr(sms_module, "CRUDAutoCard", _AutoCard)
    monkeypatch.setattr(
        sms_module.SettingsManager,
        "get_settings",
        AsyncMock(return_value=SimpleNamespace(auto_bonus_enabled=True, auto_bonus_percent=10)),
    )
    monkeypatch.setattr(sms_module, "_process_payment", processed)
    return processed


class TestFallbackAmount:
    @pytest.mark.asyncio
    async def test_bank_rule_wins_over_forwarder_amount(self, monkeypatch):
        claimed: list[int] = []
        _patch_auto_card(monkeypatch, claimed)
        monkeypatch.setattr(
            sms_module, "extract_deposit_rial", lambda text: SimpleNamespace(amount_rial=500, bank_id="x")
        )
        await sms_module.process_payment_sms("sms", fallback_amount_rial=999, is_deposit=True)
        assert claimed == [500]

    @pytest.mark.asyncio
    async def test_forwarder_amount_used_when_no_rule_matches(self, monkeypatch):
        claimed: list[int] = []
        processed = _patch_auto_card(monkeypatch, claimed)
        monkeypatch.setattr(sms_module, "extract_deposit_rial", lambda text: None)
        await sms_module.process_payment_sms("sms", fallback_amount_rial=999, is_deposit=True)
        assert claimed == [999]
        processed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_forwarder_amount_ignored_for_withdrawal(self, monkeypatch):
        claimed: list[int] = []
        _patch_auto_card(monkeypatch, claimed)
        log = AsyncMock()
        monkeypatch.setattr(sms_module, "extract_deposit_rial", lambda text: None)
        monkeypatch.setattr(sms_module, "enqueue", log)
        await sms_module.process_payment_sms("sms", fallback_amount_rial=999, is_deposit=False)
        assert claimed == []
        log.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unparsed_deposit_is_reported(self, monkeypatch):
        claimed: list[int] = []
        _patch_auto_card(monkeypatch, claimed)
        log = AsyncMock()
        monkeypatch.setattr(sms_module, "extract_deposit_rial", lambda text: None)
        monkeypatch.setattr(sms_module, "enqueue", log)
        await sms_module.process_payment_sms("واریز <b>x</b>")
        assert claimed == []
        log.assert_awaited_once()
        assert "&lt;b&gt;" in log.await_args.kwargs["message"]

    @pytest.mark.asyncio
    async def test_unrelated_sms_is_not_reported(self, monkeypatch):
        _patch_auto_card(monkeypatch, [])
        log = AsyncMock()
        monkeypatch.setattr(sms_module, "extract_deposit_rial", lambda text: None)
        monkeypatch.setattr(sms_module, "enqueue", log)
        await sms_module.process_payment_sms("your OTP is 12345")
        log.assert_not_awaited()


def _patch_payment_flow(monkeypatch, *, financial_failure=False, side_effect_failure=None):
    state = {"attempts": 0, "credits": 0}
    invoice = SimpleNamespace(code=321, id=5, amount=1_000_123, first_amount=100_000, time=1)
    result = AutoCardPaymentResult(invoice=invoice, balance=111_000, bonus=10_000)
    cleanup = AsyncMock(return_value=True)

    class AutoCard:
        async def approve_and_credit(self, amount, *, bonus_enabled, bonus_percent):
            assert (amount, bonus_enabled, bonus_percent) == (1_000_123, True, 10)
            state["attempts"] += 1
            if financial_failure and state["attempts"] == 1:
                raise RuntimeError("database unavailable")
            if state["credits"]:
                return None
            state["credits"] += 1
            return result

        delete = cleanup

    stats = AsyncMock(return_value={"manual_approved": 0, "manual_rejected": 0, "auto_approved": 1, "auto_rejected": 0})
    notify = AsyncMock()
    log = AsyncMock()
    boundaries = {"notify": notify, "stats": stats, "log": log, "cleanup": cleanup}
    if side_effect_failure:
        boundaries[side_effect_failure].side_effect = RuntimeError("post-commit unavailable")
    _set_secret(monkeypatch, _SECRET)
    monkeypatch.setattr(sms_module, "CRUDAutoCard", AutoCard)
    monkeypatch.setattr(sms_module, "extract_deposit_rial", lambda text: None)
    monkeypatch.setattr(
        sms_module.SettingsManager,
        "get_settings",
        AsyncMock(return_value=SimpleNamespace(auto_bonus_enabled=True, auto_bonus_percent=10)),
    )
    monkeypatch.setattr(sms_module, "_notify_user", notify)
    monkeypatch.setattr(sms_module, "_get_user_transaction_stats", stats)
    monkeypatch.setattr(sms_module, "_log_payment", log)
    return state, result, boundaries


async def test_financial_failure_returns_500_and_retry_can_succeed(client, monkeypatch, fake_redis):
    state, result, boundaries = _patch_payment_flow(monkeypatch, financial_failure=True)
    first = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
    assert first.status_code == 500
    assert state["credits"] == 0
    boundaries["notify"].assert_not_awaited()
    boundaries["cleanup"].assert_not_awaited()
    retry = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
    assert retry.json() == {"status": "success"}
    assert (state["attempts"], state["credits"]) == (2, 1)
    boundaries["notify"].assert_awaited_once_with(result.invoice, 111_000, 10_000, 10)
    boundaries["cleanup"].assert_awaited_once_with(result.invoice.code)


@pytest.mark.parametrize("failure", ["notify", "stats", "log", "cleanup"])
async def test_post_commit_notification_failure_returns_success_without_recredit(
    client, monkeypatch, fake_redis, failure
):
    state, result, boundaries = _patch_payment_flow(monkeypatch, side_effect_failure=failure)
    first = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
    retry = await client.post(
        "/api/sms", json={**_FORAPP_BODY, "id": "another-delivery"}, headers={"X-API-Key": _SECRET}
    )
    assert first.json() == retry.json() == {"status": "success"}
    assert (state["attempts"], state["credits"]) == (2, 1)
    boundaries["cleanup"].assert_awaited_once_with(result.invoice.code)
    if failure == "stats":
        boundaries["log"].assert_not_awaited()
    else:
        boundaries["log"].assert_awaited_once()


async def test_duplicate_without_redis_does_not_recredit(client, monkeypatch):
    state, _, boundaries = _patch_payment_flow(monkeypatch)
    monkeypatch.setattr(sms_module, "get_redis", AsyncMock(return_value=None))
    first = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
    retry = await client.post("/api/sms", json=_FORAPP_BODY, headers={"X-API-Key": _SECRET})
    assert first.json() == retry.json() == {"status": "success"}
    assert (state["attempts"], state["credits"]) == (2, 1)
    boundaries["notify"].assert_awaited_once()
    boundaries["cleanup"].assert_awaited_once_with(321)

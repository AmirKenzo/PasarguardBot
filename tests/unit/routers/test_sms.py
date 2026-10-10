from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import sms as sms_module
from app.routers.sms import sms_router

_SECRET = "s3cr3t-sms-key-0123456789"
_REJECTED = {"Telegram": "@AmirKenzoo"}


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
    monkeypatch.setattr(sms_module.config, "SMS_WEBHOOK_SECRET", value)


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
        assert response.json() == _REJECTED
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wrong_key_is_rejected(self, client, process_mock, monkeypatch):
        _set_secret(monkeypatch, _SECRET)
        response = await client.post("/api/sms", json={"text": "deposit"}, headers={"x-api-key": "wrong"})
        assert response.json() == _REJECTED
        process_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_key_is_rejected(self, client, process_mock, monkeypatch):
        _set_secret(monkeypatch, _SECRET)
        response = await client.post("/api/sms", json={"text": "deposit"})
        assert response.json() == _REJECTED
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
        process_mock.assert_awaited_once_with("deposit")

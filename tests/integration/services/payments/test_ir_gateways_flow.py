"""Iranian direct gateways: the shared deposit -> verify -> credit flow, run for every provider.

Each provider talks to a fake API (httpx.MockTransport) that answers like the real one, so the
same scenarios prove both the provider adapters and the shared service.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import ir_gateway_payments
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.db.models.user import User
from app.services.payments.ir_gateways import config, service
from app.services.payments.ir_gateways.providers import GATEWAYS, GatewayError

ADMIN = 1001
USER = 2002
KEYS = list(GATEWAYS)
LIVE_MERCHANTS = {"zarinpal": "1344b5d4-0048-11e8-94db-005056a205be", "zibal": "5c9a4e6e18f93460ad8ef6b6"}


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


class FakeApi:
    """Answers Zarinpal v4 and Zibal v1 like the real services, driven by `paid` / `mismatch`."""

    def __init__(self) -> None:
        self.paid = False
        self.mismatch = False  # the gateway reports a different amount than was requested
        self.requested: dict[str, int] = {}
        self.orders: dict[str, str] = {}
        self.calls: list[tuple[str, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        path = request.url.path
        self.calls.append((path, body))
        if path == "/pg/v4/payment/request.json":
            authority = f"S{len(self.requested):035d}"
            self.requested[authority] = body["amount"]
            return httpx.Response(200, json={"data": {"code": 100, "authority": authority}, "errors": []})
        if path == "/pg/v4/payment/verify.json":
            if self.paid and self.mismatch:
                return self._zp_error(-50)
            if self.paid and body["amount"] == self.requested.get(body["authority"]):
                data = {"code": 100, "ref_id": 201, "card_pan": "502229******5995"}
                return httpx.Response(200, json={"data": data, "errors": []})
            return self._zp_error(-51)
        if path == "/v1/request":
            track_id = 4840000000 + len(self.requested)
            self.requested[str(track_id)] = body["amount"]
            self.orders[str(track_id)] = body["orderId"]
            return httpx.Response(200, json={"message": "success", "result": 100, "trackId": track_id})
        if path in ("/v1/verify", "/v1/inquiry"):
            track_id = str(body["trackId"])
            if not self.paid:
                return httpx.Response(200, json={"message": "transaction failed", "result": 202})
            amount = self.requested[track_id] // 10 if self.mismatch else self.requested[track_id]
            data = {"amount": amount, "refNumber": 98765, "cardNumber": "62741****44", "orderId": self.orders[track_id]}
            return httpx.Response(200, json={"message": "success", "result": 100, **data})
        return httpx.Response(404, json={})

    @staticmethod
    def _zp_error(code: int) -> httpx.Response:
        error = {"code": code, "message": "error", "validations": []}
        return httpx.Response(401 if code == -51 else 200, json={"data": {}, "errors": error})


def _callback_query(key: str, authority: str, *, ok: bool) -> dict[str, str]:
    if key == "zarinpal":
        return {"Authority": authority, "Status": "OK" if ok else "NOK"}
    return {"trackId": authority, "success": "1" if ok else "0", "status": "2"}


def _gateway_values(**overrides) -> dict:
    values = {
        "enabled": True,
        "sandbox": True,
        "merchant": "",
        "deposit_min": 1000,
        "deposit_max": 1_000_000,
        "bonus_enabled": True,
        "bonus_percent": 10,
    }
    values.update(overrides)
    return values


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, tmp_path) -> FakeApi:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'irgw.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(
                IrGatewayPayment.metadata.create_all, tables=[IrGatewayPayment.__table__, User.__table__]
            )
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=ADMIN, amount=0), User(id=USER, amount=0)])
            await session.commit()
        return maker

    monkeypatch.setattr(ir_gateway_payments, "Session", asyncio.run(setup()))
    fake = FakeApi()
    transport = httpx.MockTransport(fake.handler)
    for provider in GATEWAYS.values():
        monkeypatch.setattr(provider, "transport", transport)

    settings = SimpleNamespace(id=1, ir_gateways={key: _gateway_values() for key in KEYS})
    monkeypatch.setattr(service, "SettingsManager", lambda: SimpleNamespace(get_settings=_async(settings)))
    monkeypatch.setattr(config, "WEBAPP_URL", "https://bot.example.com")
    monkeypatch.setattr(config, "ADMIN_ID", [ADMIN])
    monkeypatch.setattr(service, "send_log_message", _async(None))
    monkeypatch.setattr(service, "try_fulfill_after_crypto_credit", _async(False))
    monkeypatch.setattr(service, "cancel_after_crypto_expire", _async(None))
    monkeypatch.setattr(service, "Kenzo", SimpleNamespace(send_message=_async(None)))
    fake.settings = settings
    return fake


async def _balance(user_id: int) -> int:
    async with ir_gateway_payments.Session() as session:
        return int((await session.execute(select(User.amount).where(User.id == user_id))).scalar_one())


@pytest.mark.parametrize("key", KEYS)
def test_paid_payment_credits_once_with_bonus(api: FakeApi, key: str) -> None:
    async def scenario():
        payment = await service.create_deposit(key, ADMIN, 50_000, source="bot")
        assert payment.gateway == key and payment.order_id.startswith(GATEWAYS[key].order_prefix)
        assert api.requested[payment.authority] == 500_000  # toman -> rial
        assert service.payment_url(payment).endswith(payment.authority)
        api.paid = True
        first = await service.handle_callback(key, _callback_query(key, payment.authority, ok=True))
        again = await ir_gateway_payments.IrGatewayPaymentCRUD().get(payment.id)
        second = await service.verify_payment(again)
        return first, second, await _balance(ADMIN)

    first, second, balance = asyncio.run(scenario())
    assert first.status == "completed" and first.ref_id and first.card_pan
    assert second.status == "completed"
    assert balance == 55_000  # 50,000 + 10% bonus, credited exactly once


@pytest.mark.parametrize("key", KEYS)
def test_spoofed_success_waits_and_buyer_cancel_closes(api: FakeApi, key: str) -> None:
    async def scenario():
        payment = await service.create_deposit(key, ADMIN, 20_000, source="webapp")
        waiting = await service.handle_callback(key, _callback_query(key, payment.authority, ok=True))
        canceled = await service.handle_callback(key, _callback_query(key, payment.authority, ok=False))
        return waiting, canceled, await _balance(ADMIN)

    waiting, canceled, balance = asyncio.run(scenario())
    assert waiting.status == "pending"  # the query string alone never credits
    assert canceled.status == "canceled"
    assert balance == 0


@pytest.mark.parametrize("key", KEYS)
def test_amount_mismatch_is_never_credited(api: FakeApi, key: str) -> None:
    async def scenario():
        payment = await service.create_deposit(key, ADMIN, 50_000, source="bot")
        api.paid, api.mismatch = True, True
        return await service.verify_payment(payment), await _balance(ADMIN)

    result, balance = asyncio.run(scenario())
    assert result.status == "failed"
    assert balance == 0


@pytest.mark.parametrize("key", KEYS)
def test_stale_unpaid_payment_expires(api: FakeApi, key: str) -> None:
    async def scenario():
        payment = await service.create_deposit(key, ADMIN, 20_000, source="bot")
        old = int(time.time()) - service.LOCAL_EXPIRY_SECONDS - 5
        payment = await ir_gateway_payments.IrGatewayPaymentCRUD().update(payment.id, created_at=old)
        return await service.verify_payment(payment)

    assert asyncio.run(scenario()).status == "expired"


@pytest.mark.parametrize("key", KEYS)
def test_sandbox_is_admin_only_and_limits_apply(api: FakeApi, key: str) -> None:
    async def scenario():
        with pytest.raises(GatewayError):
            await service.create_deposit(key, USER, 50_000, source="bot")
        with pytest.raises(GatewayError):
            await service.create_deposit(key, ADMIN, 500, source="bot")
        with pytest.raises(GatewayError):
            await service.create_deposit(key, ADMIN, 2_000_000, source="bot")

    asyncio.run(scenario())
    assert config.is_available_for(api.settings, key, ADMIN)
    assert not config.is_available_for(api.settings, key, USER)


@pytest.mark.parametrize("key", KEYS)
def test_live_mode_needs_a_valid_merchant(api: FakeApi, key: str) -> None:
    api.settings.ir_gateways[key] = _gateway_values(sandbox=False)
    assert not config.is_ready(api.settings, key)
    api.settings.ir_gateways[key]["merchant"] = LIVE_MERCHANTS[key]
    assert GATEWAYS[key].is_valid_merchant(LIVE_MERCHANTS[key])
    assert config.is_available_for(api.settings, key, USER)
    assert config.merchant_for(api.settings, key) == LIVE_MERCHANTS[key]
    assert not GATEWAYS[key].is_valid_merchant("bad merchant!")


def test_open_payment_cap_is_shared_across_gateways(api: FakeApi) -> None:
    async def scenario():
        for index in range(service.MAX_OPEN_PAYMENTS):
            await service.create_deposit(KEYS[index % len(KEYS)], ADMIN, 10_000, source="bot")
        with pytest.raises(GatewayError):
            await service.create_deposit(KEYS[-1], ADMIN, 10_000, source="bot")

    asyncio.run(scenario())


def test_saving_one_gateway_leaves_the_others_untouched(api: FakeApi) -> None:
    before = {key: dict(values) for key, values in api.settings.ir_gateways.items()}
    updated = config.updated_settings(api.settings, KEYS[0], enabled=False, bonus_percent=25, unknown="x")
    assert updated[KEYS[0]]["enabled"] is False and updated[KEYS[0]]["bonus_percent"] == 25
    assert "unknown" not in updated[KEYS[0]]
    assert all(updated[key] == before[key] for key in KEYS[1:])
    assert api.settings.ir_gateways == before  # the live settings object is never mutated
    assert config.gateway_settings(SimpleNamespace(ir_gateways={}), KEYS[0]) == config.DEFAULT_GATEWAY_SETTINGS


def test_unknown_authority_and_gateway(api: FakeApi) -> None:
    assert asyncio.run(service.handle_callback(KEYS[0], _callback_query(KEYS[0], "missing", ok=True))) is None
    with pytest.raises(GatewayError):
        asyncio.run(service.create_deposit("nope", ADMIN, 10_000, source="bot"))


@pytest.mark.parametrize("key", KEYS)
def test_callback_page_renders_result(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.webhook import ir_gateways as callback_route, payment_page

    paid = SimpleNamespace(
        status="completed", amount=50_000, ref_id="<201>", sandbox=True, order_id="ZP1", card_pan="5022****5995"
    )
    seen: list[tuple[str, dict]] = []

    async def fake_handle(gateway: str, query):
        seen.append((gateway, dict(query)))
        return paid if "found" in query.values() else None

    monkeypatch.setattr(callback_route, "handle_callback", fake_handle)
    monkeypatch.setattr(payment_page, "_bot_link", _async("https://t.me/test_bot"))
    app = FastAPI()
    app.include_router(callback_route.router, prefix="/api")
    client = TestClient(app)

    ok = client.get(f"/api/payments/{key}/callback", params=_callback_query(key, "found", ok=True))
    assert ok.status_code == 200
    assert "50,000" in ok.text and "&lt;201&gt;" in ok.text and GATEWAYS[key].title in ok.text
    assert seen[0][0] == key
    missing = client.get(f"/api/payments/{key}/callback", params=_callback_query(key, "nope", ok=True))
    assert missing.status_code == 200 and "پیدا نشد" in missing.text
    assert client.get(f"/api/payments/{key}/callback").status_code == 200
    assert client.get("/api/payments/unknown/callback").status_code == 404

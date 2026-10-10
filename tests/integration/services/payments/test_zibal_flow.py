"""Zibal client parsing and the deposit -> verify -> credit flow against a mocked gateway."""

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

from app.db.crud import zibal_payments
from app.db.models.user import User
from app.db.models.zibal_payment import ZibalPayment
from app.services.payments import zibal, zibal_config

ADMIN = 1001
USER = 2002
TRACK_ID = 4840491172


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


class FakeGateway:
    """Answers Zibal v1 request/verify/inquiry like the real API, from a per-test script."""

    def __init__(self) -> None:
        self.verify_result = 202
        self.paid_amount: int | None = None  # rial amount Zibal reports; None means "what was requested"
        self.order_id: str | None = None
        self.requested_amount = 0
        self.calls: list[tuple[str, dict]] = []

    def _paid(self) -> dict:
        return {
            "amount": self.paid_amount if self.paid_amount is not None else self.requested_amount,
            "refNumber": 98765,
            "cardNumber": "62741****44",
            "orderId": self.order_id,
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        path = request.url.path
        self.calls.append((path, body))
        if path == "/v1/request":
            self.requested_amount = body["amount"]
            self.order_id = body["orderId"]
            return httpx.Response(200, json={"message": "success", "result": 100, "trackId": TRACK_ID})
        if path == "/v1/inquiry":
            return httpx.Response(200, json={"message": "success", "result": 100, "status": 1, **self._paid()})
        if self.verify_result == 100:
            return httpx.Response(200, json={"message": "success", "result": 100, **self._paid()})
        if self.verify_result == 201:
            return httpx.Response(200, json={"message": "already verified", "result": 201})
        return httpx.Response(200, json={"message": "transaction failed", "result": self.verify_result})


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "zibal_enabled": True,
        "zibal_sandbox": True,
        "zibal_merchant": "",
        "zibal_deposit_min": 1000,
        "zibal_deposit_max": 1_000_000,
        "zibal_bonus_enabled": True,
        "zibal_bonus_percent": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch, tmp_path) -> FakeGateway:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'zb.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(ZibalPayment.metadata.create_all, tables=[ZibalPayment.__table__, User.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=ADMIN, amount=0), User(id=USER, amount=0)])
            await session.commit()
        return maker

    monkeypatch.setattr(zibal_payments, "Session", asyncio.run(setup()))

    fake = FakeGateway()
    transport = httpx.MockTransport(fake.handler)
    original_init = zibal.ZibalClient.__init__

    def init(self, merchant, **_):
        original_init(self, merchant, transport=transport)

    monkeypatch.setattr(zibal.ZibalClient, "__init__", init)
    settings = _settings()
    monkeypatch.setattr(zibal, "SettingsManager", lambda: SimpleNamespace(get_settings=_async(settings)))
    monkeypatch.setattr(zibal_config, "WEBAPP_URL", "https://bot.example.com")
    monkeypatch.setattr(zibal_config, "ADMIN_ID", [ADMIN])
    monkeypatch.setattr(zibal, "send_log_message", _async(None))
    monkeypatch.setattr(zibal, "try_fulfill_after_crypto_credit", _async(False))
    monkeypatch.setattr(zibal, "cancel_after_crypto_expire", _async(None))
    monkeypatch.setattr(zibal, "Kenzo", SimpleNamespace(send_message=_async(None)))
    return fake


async def _balance(user_id: int) -> int:
    async with zibal_payments.Session() as session:
        return int((await session.execute(select(User.amount).where(User.id == user_id))).scalar_one())


def test_config_test_merchant_and_visibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zibal_config, "WEBAPP_URL", "https://bot.example.com")
    monkeypatch.setattr(zibal_config, "ADMIN_ID", [ADMIN])
    sandbox = _settings(zibal_merchant="realmerchant123")
    assert zibal_config.merchant_for(sandbox) == "zibal"  # test mode ignores the stored merchant
    assert zibal_config.is_available_for(sandbox, ADMIN)
    assert not zibal_config.is_available_for(sandbox, USER)

    live = _settings(zibal_sandbox=False)
    assert not zibal_config.is_ready(live)
    live.zibal_merchant = "realmerchant123"
    assert zibal_config.is_available_for(live, USER)
    assert not zibal_config.is_valid_merchant("zibal")  # the public test merchant is not a live merchant
    assert not zibal_config.is_valid_merchant("bad merchant!")


def test_paid_payment_credits_once_with_bonus(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zibal.create_deposit(ADMIN, 50_000, source="bot")
        path, body = gateway.calls[0]
        assert path == "/v1/request"
        assert body["merchant"] == "zibal" and body["amount"] == 500_000
        assert body["callbackUrl"] == "https://bot.example.com/api/payments/zibal/callback"
        assert zibal.payment_url(payment) == f"https://gateway.zibal.ir/start/{TRACK_ID}"

        gateway.verify_result = 100
        first = await zibal.handle_callback(str(TRACK_ID), "1")
        gateway.verify_result = 201  # repeat verify: no details, so inquiry fills them in
        again = await zibal_payments.ZibalPaymentCRUD().get(payment.id)
        second = await zibal.verify_payment(again)
        return first, second, await _balance(ADMIN)

    first, second, balance = asyncio.run(scenario())
    assert first.status == "completed" and first.ref_id == "98765" and first.card_pan == "62741****44"
    assert second.status == "completed"
    assert balance == 55_000  # 50,000 + 10% bonus, credited exactly once


def test_already_verified_is_credited_via_inquiry(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zibal.create_deposit(ADMIN, 20_000, source="bot")
        gateway.verify_result = 201  # e.g. verified by a previous run that crashed before crediting
        result = await zibal.verify_payment(payment)
        return result, await _balance(ADMIN), [path for path, _ in gateway.calls]

    result, balance, paths = asyncio.run(scenario())
    assert result.status == "completed" and result.ref_id == "98765"
    assert balance == 22_000
    assert paths[-2:] == ["/v1/verify", "/v1/inquiry"]


def test_amount_mismatch_is_never_credited(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zibal.create_deposit(ADMIN, 50_000, source="bot")
        gateway.verify_result = 100
        gateway.paid_amount = 10_000  # gateway says 1,000 toman were paid
        return await zibal.verify_payment(payment), await _balance(ADMIN)

    result, balance = asyncio.run(scenario())
    assert result.status == "failed"
    assert balance == 0


def test_unpaid_payment_waits_then_cancels_on_failed_return(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zibal.create_deposit(ADMIN, 20_000, source="webapp")
        waiting = await zibal.handle_callback(str(TRACK_ID), "1")  # spoofed success, gateway says 202
        canceled = await zibal.handle_callback(str(TRACK_ID), "0")
        return waiting, canceled, await _balance(ADMIN), payment

    waiting, canceled, balance, _ = asyncio.run(scenario())
    assert waiting.status == "pending"
    assert canceled.status == "canceled"
    assert balance == 0


def test_stale_unpaid_payment_expires(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zibal.create_deposit(ADMIN, 20_000, source="bot")
        old = int(time.time()) - zibal.LOCAL_EXPIRY_SECONDS - 5
        payment = await zibal_payments.ZibalPaymentCRUD().update(payment.id, created_at=old)
        return await zibal.verify_payment(payment)

    assert asyncio.run(scenario()).status == "expired"


def test_non_admin_limits_and_open_cap(gateway: FakeGateway) -> None:
    async def scenario():
        with pytest.raises(zibal.ZibalError):
            await zibal.create_deposit(USER, 50_000, source="bot")  # test mode is admin-only
        with pytest.raises(zibal.ZibalError):
            await zibal.create_deposit(ADMIN, 500, source="bot")
        for _ in range(zibal.MAX_OPEN_PAYMENTS):
            await zibal.create_deposit(ADMIN, 10_000, source="bot")
        with pytest.raises(zibal.ZibalError):
            await zibal.create_deposit(ADMIN, 10_000, source="bot")

    asyncio.run(scenario())


def test_unknown_track_id_returns_none(gateway: FakeGateway) -> None:
    assert asyncio.run(zibal.handle_callback("999", "1")) is None


def test_callback_page_renders_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.webhook import payment_page, zibal as callback_route

    paid = SimpleNamespace(
        status="completed", amount=50_000, ref_id="98765", sandbox=True, order_id="ZB1", card_pan="62741****44"
    )
    seen: list[tuple[str, str]] = []

    async def fake_handle(track_id: str, success: str):
        seen.append((track_id, success))
        return paid if track_id == "123" else None

    monkeypatch.setattr(callback_route, "handle_callback", fake_handle)
    monkeypatch.setattr(payment_page, "_bot_link", _async("https://t.me/test_bot"))
    app = FastAPI()
    app.include_router(callback_route.router, prefix="/api")
    client = TestClient(app)

    ok = client.get("/api/payments/zibal/callback", params={"success": "1", "trackId": "123", "status": "2"})
    assert ok.status_code == 200
    assert "50,000" in ok.text and "98765" in ok.text and "زیبال" in ok.text
    assert seen == [("123", "1")]
    missing = client.get("/api/payments/zibal/callback", params={"success": "1", "trackId": "nope"})
    assert missing.status_code == 200 and "پیدا نشد" in missing.text

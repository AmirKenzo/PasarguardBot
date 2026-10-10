"""Zarinpal client parsing and the deposit -> verify -> credit flow against a mocked gateway."""

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

from app.db.crud import zarinpal_payments
from app.db.models.user import User
from app.db.models.zarinpal_payment import ZarinpalPayment
from app.services.payments import zarinpal, zarinpal_config

ADMIN = 1001
USER = 2002


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


class FakeGateway:
    """Answers Zarinpal v4 request/verify like the real API, from a per-test script."""

    def __init__(self) -> None:
        self.verify_code = -51
        self.requests: list[tuple[str, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append((request.url.path, body))
        if request.url.path.endswith("/request.json"):
            return httpx.Response(200, json={"data": {"code": 100, "authority": "S" + "0" * 35}, "errors": []})
        if self.verify_code in zarinpal.SUCCESS_CODES:
            data = {"code": self.verify_code, "ref_id": 201, "card_pan": "502229******5995"}
            return httpx.Response(200, json={"data": data, "errors": []})
        error = {"code": self.verify_code, "message": "Session is not active paid try.", "validations": []}
        return httpx.Response(200, json={"data": [], "errors": error})


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "zarinpal_enabled": True,
        "zarinpal_sandbox": True,
        "zarinpal_merchant_id": "",
        "zarinpal_deposit_min": 1000,
        "zarinpal_deposit_max": 1_000_000,
        "zarinpal_bonus_enabled": True,
        "zarinpal_bonus_percent": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch, tmp_path) -> FakeGateway:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'zp.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(ZarinpalPayment.metadata.create_all, tables=[ZarinpalPayment.__table__, User.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=ADMIN, amount=0), User(id=USER, amount=0)])
            await session.commit()
        return maker

    monkeypatch.setattr(zarinpal_payments, "Session", asyncio.run(setup()))

    fake = FakeGateway()
    transport = httpx.MockTransport(fake.handler)
    original_init = zarinpal.ZarinpalClient.__init__

    def init(self, merchant_id, sandbox, **_):
        original_init(self, merchant_id, sandbox, transport=transport)

    monkeypatch.setattr(zarinpal.ZarinpalClient, "__init__", init)

    settings = _settings()
    monkeypatch.setattr(zarinpal, "SettingsManager", lambda: SimpleNamespace(get_settings=_async(settings)))
    monkeypatch.setattr(zarinpal_config, "WEBAPP_URL", "https://bot.example.com")
    monkeypatch.setattr(zarinpal_config, "ADMIN_ID", [ADMIN])
    monkeypatch.setattr(zarinpal, "send_log_message", _async(None))
    monkeypatch.setattr(zarinpal, "try_fulfill_after_crypto_credit", _async(False))
    monkeypatch.setattr(zarinpal, "cancel_after_crypto_expire", _async(None))
    monkeypatch.setattr(zarinpal, "Kenzo", SimpleNamespace(send_message=_async(None)))
    fake.settings = settings
    return fake


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


async def _balance(user_id: int) -> int:
    async with zarinpal_payments.Session() as session:
        return int((await session.execute(select(User.amount).where(User.id == user_id))).scalar_one())


def test_parse_reads_both_envelopes() -> None:
    assert zarinpal._parse({"data": {"code": 100, "authority": "A1"}, "errors": []}) == (
        100,
        {"code": 100, "authority": "A1"},
        None,
    )
    code, data, message = zarinpal._parse({"data": [], "errors": {"code": -9, "message": "bad"}})
    assert (code, data, message) == (-9, {}, "bad")
    assert zarinpal._parse("oops")[0] is None


def test_sandbox_merchant_fallback_and_visibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zarinpal_config, "WEBAPP_URL", "https://bot.example.com")
    monkeypatch.setattr(zarinpal_config, "ADMIN_ID", [ADMIN])
    sandbox = _settings()
    assert zarinpal_config.merchant_id_for(sandbox) == zarinpal_config.SANDBOX_MERCHANT_ID
    assert zarinpal_config.is_available_for(sandbox, ADMIN)
    assert not zarinpal_config.is_available_for(sandbox, USER)

    live = _settings(zarinpal_sandbox=False)
    assert not zarinpal_config.is_ready(live)  # live mode needs a real merchant id
    live.zarinpal_merchant_id = "1344b5d4-0048-11e8-94db-005056a205be"
    assert zarinpal_config.is_available_for(live, USER)

    monkeypatch.setattr(zarinpal_config, "WEBAPP_URL", "http://insecure.example.com")
    assert not zarinpal_config.is_ready(live)  # no https callback, no gateway


def test_non_admin_cannot_use_sandbox(gateway: FakeGateway) -> None:
    with pytest.raises(zarinpal.ZarinpalError):
        asyncio.run(zarinpal.create_deposit(USER, 50_000, source="bot"))


def test_paid_payment_credits_once_with_bonus(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zarinpal.create_deposit(ADMIN, 50_000, source="bot")
        path, body = gateway.requests[0]
        assert path == "/pg/v4/payment/request.json"
        assert body["amount"] == 500_000  # toman -> rial
        assert body["callback_url"] == "https://bot.example.com/api/payments/zarinpal/callback"
        assert zarinpal.payment_url(payment).startswith("https://sandbox.zarinpal.com/pg/StartPay/S")

        gateway.verify_code = 100
        first = await zarinpal.handle_callback(payment.authority, "OK")
        gateway.verify_code = 101  # Zarinpal's "already verified" on the second call
        second = await zarinpal.verify_payment(await zarinpal_payments.ZarinpalPaymentCRUD().get(payment.id))
        return first, second, await _balance(ADMIN)

    first, second, balance = asyncio.run(scenario())
    assert first.status == "completed" and first.ref_id == "201"
    assert second.status == "completed"
    assert balance == 55_000  # 50,000 + 10% bonus, credited exactly once


def test_unpaid_payment_waits_then_cancels_on_nok(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zarinpal.create_deposit(ADMIN, 20_000, source="webapp")
        waiting = await zarinpal.verify_payment(payment)
        canceled = await zarinpal.handle_callback(payment.authority, "NOK")
        return waiting, canceled, await _balance(ADMIN)

    waiting, canceled, balance = asyncio.run(scenario())
    assert waiting.status == "pending"
    assert canceled.status == "canceled"
    assert balance == 0


def test_spoofed_ok_callback_does_not_credit(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zarinpal.create_deposit(ADMIN, 20_000, source="bot")
        result = await zarinpal.handle_callback(payment.authority, "OK")  # gateway still says -51
        return result, await _balance(ADMIN)

    result, balance = asyncio.run(scenario())
    assert result.status == "pending"
    assert balance == 0


def test_stale_unpaid_payment_expires(gateway: FakeGateway) -> None:
    async def scenario():
        payment = await zarinpal.create_deposit(ADMIN, 20_000, source="bot")
        old = int(time.time()) - zarinpal.LOCAL_EXPIRY_SECONDS - 5
        payment = await zarinpal_payments.ZarinpalPaymentCRUD().update(payment.id, created_at=old)
        return await zarinpal.verify_payment(payment)

    assert asyncio.run(scenario()).status == "expired"


def test_amount_limits_and_open_cap(gateway: FakeGateway) -> None:
    async def scenario():
        with pytest.raises(zarinpal.ZarinpalError):
            await zarinpal.create_deposit(ADMIN, 500, source="bot")
        for _ in range(zarinpal.MAX_OPEN_PAYMENTS):
            await zarinpal.create_deposit(ADMIN, 10_000, source="bot")
        with pytest.raises(zarinpal.ZarinpalError):
            await zarinpal.create_deposit(ADMIN, 10_000, source="bot")

    asyncio.run(scenario())


def test_unknown_authority_returns_none(gateway: FakeGateway) -> None:
    assert asyncio.run(zarinpal.handle_callback("S-missing", "OK")) is None


def test_callback_page_renders_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.webhook import zarinpal as callback_route

    paid = SimpleNamespace(status="completed", amount=50_000, ref_id="<201>", sandbox=True)
    seen: list[tuple[str, str]] = []

    async def fake_handle(authority: str, status: str):
        seen.append((authority, status))
        return paid if authority == "S1" else None

    monkeypatch.setattr(callback_route, "handle_callback", fake_handle)
    monkeypatch.setattr(callback_route, "_bot_link", _async("https://t.me/test_bot"))
    app = FastAPI()
    app.include_router(callback_route.router, prefix="/api")
    client = TestClient(app)

    ok = client.get("/api/payments/zarinpal/callback", params={"Authority": "S1", "Status": "OK"})
    assert ok.status_code == 200
    assert "50,000" in ok.text and "&lt;201&gt;" in ok.text and "https://t.me/test_bot" in ok.text
    assert seen == [("S1", "OK")]

    missing = client.get("/api/payments/zarinpal/callback", params={"Authority": "nope", "Status": "OK"})
    assert missing.status_code == 200 and "پیدا نشد" in missing.text
    assert client.get("/api/payments/zarinpal/callback").status_code == 200

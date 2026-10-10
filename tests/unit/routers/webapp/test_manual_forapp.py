"""WebApp manual top-up with ForApp: reserve on deposit, reuse/refuse on receipt, status poll."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.models.webapp.balance import BalanceDepositManualRequest
from app.routers.webapp import balance

USER_ID = 7


def _settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "pay_mode": True,
        "manual_deposit_min": 1000,
        "manual_deposit_max": 1_000_000,
        "manual_card_random_mode": False,
        "forapp_enabled": True,
        "forapp_offset_min": 1,
        "forapp_offset_max": 999,
        "forapp_ttl_minutes": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 200, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(content: bytes) -> SimpleNamespace:
    async def read() -> bytes:
        return content

    return SimpleNamespace(filename="receipt.png", content_type="image/png", read=read)


def _base_env(monkeypatch) -> SimpleNamespace:
    state = SimpleNamespace(created=[], updated=[])

    async def authenticate_user(**kwargs: Any) -> int:
        return USER_ID

    async def get_settings(self):
        return _settings()

    async def read_user(self, user_id: int):
        return SimpleNamespace(id=user_id, number="989000000000", amount=0)

    async def get_all_cards(self):
        return [SimpleNamespace(number="6037991234567890", name="Dev", active=True)]

    async def reserve(base: int, **kwargs: Any):
        return base + 21, 21

    async def create(self, user_id: int, amount: int, method: str, **kwargs: Any):
        tx = SimpleNamespace(
            id=len(state.created) + 1,
            user_id=user_id,
            amount=amount,
            method=method,
            status="pending",
            payable_amount=kwargs.get("payable_amount"),
            auto_approve_at=None,
        )
        state.created.append(tx)
        return tx

    async def try_insert(self, phash: str, user_id: int):
        return SimpleNamespace(phash=phash)

    async def update_transaction_id(self, phash: str, tx_id: int) -> bool:
        return True

    async def schedule(self, tx):
        return None

    async def get(self, tx_id: int):
        return next((t for t in state.created if t.id == tx_id), None)

    monkeypatch.setattr(balance, "authenticate_user", authenticate_user)
    monkeypatch.setattr(balance, "_phone_verify_required", lambda settings, user: False)
    monkeypatch.setattr(balance.SettingsManager, "get_settings", get_settings)
    monkeypatch.setattr(balance.UserCRUD, "read_user", read_user)
    monkeypatch.setattr(balance.ManualCardManager, "get_all_cards", get_all_cards)
    monkeypatch.setattr(balance, "reserve_unique_payable_for_manual", reserve)
    monkeypatch.setattr(balance.TransactionCRUD, "create", create)
    monkeypatch.setattr(balance.TransactionCRUD, "get", get)
    monkeypatch.setattr(balance.ReceiptHashCRUD, "try_insert", try_insert)
    monkeypatch.setattr(balance.ReceiptHashCRUD, "update_transaction_id", update_transaction_id)
    monkeypatch.setattr(balance.ManualAutoApproveRuleCRUD, "schedule_for_transaction", schedule)
    monkeypatch.setattr(balance.ManualAutoApproveRuleCRUD, "format_status_line", lambda *a, **k: "")
    monkeypatch.setattr(balance.TransactionCRUD, "count_user_transactions", lambda *a, **k: asyncio.sleep(0, result=0))

    async def no_log_channel(self, *args: Any, **kwargs: Any):
        return None

    monkeypatch.setattr(balance.LogChannelManager, "get_log_channel_destination", no_log_channel)
    return state


def _deposit(amount: int = 50_000):
    return asyncio.run(
        balance.deposit_manual(BalanceDepositManualRequest(amount=amount))
    )


def test_deposit_manual_reserves_unique_payable(monkeypatch) -> None:
    state = _base_env(monkeypatch)
    res = _deposit()
    assert res.ok is True
    assert res.forapp_enabled is True
    assert res.payable_amount == 50_021
    assert res.payable_rial == 500_210
    assert res.tx_id == 1
    assert state.created[0].payable_amount == 50_021


def test_deposit_manual_falls_back_without_forapp(monkeypatch) -> None:
    state = _base_env(monkeypatch)

    async def get_settings(self):
        return _settings(forapp_enabled=False)

    monkeypatch.setattr(balance.SettingsManager, "get_settings", get_settings)
    res = _deposit()
    assert res.ok is True
    assert res.forapp_enabled is False
    assert res.payable_amount is None
    assert state.created == []


def test_receipt_reuses_pending_payable_tx(monkeypatch) -> None:
    _base_env(monkeypatch)
    created_ids = []

    async def create(self, user_id: int, amount: int, method: str, **kwargs: Any):
        created_ids.append(amount)
        raise AssertionError("must reuse the reserved tx, not create one")

    async def find_pending(self, payable: int, since_ts=None):
        assert payable == 50_021
        return SimpleNamespace(id=9, user_id=USER_ID, amount=50_000, status="pending", payable_amount=50_021)

    monkeypatch.setattr(balance.TransactionCRUD, "create", create)
    monkeypatch.setattr(balance.TransactionCRUD, "find_pending_manual_by_payable", find_pending)
    res = asyncio.run(balance.deposit_manual_receipt(amount=50_021, file=_upload(_png())))
    assert res.ok is True
    assert res.already_approved is False
    assert created_ids == []


def test_receipt_refused_after_auto_approval(monkeypatch) -> None:
    _base_env(monkeypatch)

    async def find_pending(payable: int, since_ts=None):
        return None

    async def find_approved(self, user_id: int, since_ts: int):
        return SimpleNamespace(id=9, user_id=user_id, payable_amount=50_021, amount=50_000)

    async def create(self, user_id: int, amount: int, method: str, **kwargs: Any):
        raise AssertionError("must not create a tx for an already-credited transfer")

    monkeypatch.setattr(balance.TransactionCRUD, "find_pending_manual_by_payable", find_pending)
    monkeypatch.setattr(balance.TransactionCRUD, "find_recent_approved_payable_without_receipt", find_approved)
    monkeypatch.setattr(balance.TransactionCRUD, "create", create)
    res = asyncio.run(balance.deposit_manual_receipt(amount=50_021, file=_upload(_png())))
    assert res.ok is True
    assert res.already_approved is True


def test_status_endpoint_returns_own_tx_only(monkeypatch) -> None:
    _base_env(monkeypatch)

    async def get(self, tx_id: int):
        return SimpleNamespace(id=3, user_id=USER_ID, method="manual", status="approved", payable_amount=50_021)

    async def authenticate_user(**kwargs: Any) -> int:
        return USER_ID

    monkeypatch.setattr(balance.TransactionCRUD, "get", get)
    from app.models.webapp.balance import BalanceDepositManualStatusRequest

    res = asyncio.run(balance.deposit_manual_status(BalanceDepositManualStatusRequest(tx_id=3)))
    assert res.ok is True and res.status == "approved" and res.payable_amount == 50_021

    async def get_other(self, tx_id: int):
        return SimpleNamespace(id=3, user_id=USER_ID + 1, method="manual", status="pending", payable_amount=None)

    monkeypatch.setattr(balance.TransactionCRUD, "get", get_other)
    denied = asyncio.run(balance.deposit_manual_status(BalanceDepositManualStatusRequest(tx_id=3)))
    assert denied.ok is False

"""Notification failures after money is committed must be logged and must not undo the credit."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from telethon import errors

from app.jobs.payments import manual_card, trx

TX_ID = 4242
USER_ID = 777


@pytest.fixture
def captured(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """App loggers do not propagate to root, so attach the caplog handler directly."""
    loggers = [manual_card.logger, trx.logger]
    for log in loggers:
        log.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG)
    try:
        yield caplog
    finally:
        for log in loggers:
            log.removeHandler(caplog.handler)


class _FakeTransactionCRUD:
    approved: ClassVar[list[int]] = []

    async def get_pending_manual_due_auto_approve(self, now: int) -> list[Any]:
        return [SimpleNamespace(id=TX_ID, user_id=USER_ID, amount=50_000, status="pending", created_at=0)]

    async def approve_manual(self, tx: Any) -> dict[str, Any]:
        self.approved.append(tx.id)
        return {"new_balance": 150_000, "bonus": 0, "total": 50_000, "completed_at": 1}


class _FailingBot:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        raise self.exc

    async def delete_messages(self, *args: Any, **kwargs: Any) -> None:
        return None


def _patch_manual_card(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    settings = SimpleNamespace(manual_auto_confirm=True, manual_bonus_percent=0)

    async def get_settings(self: Any) -> Any:
        return settings

    async def not_fulfilled(tx_id: int) -> bool:
        return False

    async def bot_text(**kwargs: Any) -> str:
        return "{user_id} {amount} {bonus_line}"

    _FakeTransactionCRUD.approved = []
    monkeypatch.setattr(manual_card.SettingsManager, "get_settings", get_settings)
    monkeypatch.setattr(manual_card, "TransactionCRUD", _FakeTransactionCRUD)
    monkeypatch.setattr(manual_card, "try_fulfill_after_manual_credit", not_fulfilled)
    monkeypatch.setattr(manual_card, "get_bot_text", bot_text)
    monkeypatch.setattr(manual_card, "Kenzo", _FailingBot(exc))


def test_manual_card_notify_failure_is_logged_and_credit_kept(
    monkeypatch: pytest.MonkeyPatch, captured: pytest.LogCaptureFixture
) -> None:
    _patch_manual_card(monkeypatch, RuntimeError("telegram down"))

    asyncio.run(manual_card.ManualCardProcessor().check_payments())

    assert _FakeTransactionCRUD.approved == [TX_ID]
    errors_logged = [r for r in captured.records if r.levelno == logging.ERROR]
    assert any(f"tx_id={TX_ID}" in r.getMessage() and r.exc_info for r in errors_logged)


def test_manual_card_blocked_user_logs_quiet_warning(
    monkeypatch: pytest.MonkeyPatch, captured: pytest.LogCaptureFixture
) -> None:
    _patch_manual_card(monkeypatch, errors.UserIsBlockedError(request=None))

    asyncio.run(manual_card.ManualCardProcessor().check_payments())

    assert _FakeTransactionCRUD.approved == [TX_ID]
    assert not [r for r in captured.records if r.levelno >= logging.ERROR]
    assert any(r.levelno == logging.WARNING and f"tx_id={TX_ID}" in r.getMessage() for r in captured.records)


def test_trx_expire_notify_failure_is_logged_and_expiry_kept(
    monkeypatch: pytest.MonkeyPatch, captured: pytest.LogCaptureFixture
) -> None:
    expired: list[int] = []

    async def expire_payment(self: Any, order_id: int) -> bool:
        expired.append(order_id)
        return True

    async def cancel_after_expire(order_id: int) -> None:
        return None

    monkeypatch.setattr(trx.CryptoPaymentsCRUD, "expire_payment", expire_payment)
    monkeypatch.setattr(trx, "cancel_after_crypto_expire", cancel_after_expire)
    monkeypatch.setattr(trx, "Kenzo", _FailingBot(RuntimeError("telegram down")))
    payment = SimpleNamespace(order_id=99_001, user_id=USER_ID, msg_id=None, amount_irt=100_000, amount="10.5")
    settings = SimpleNamespace(arz_usd=60, arz_trx=20)

    asyncio.run(trx.TRXProcessor()._expire_payment(payment, settings))

    assert expired == [99_001]
    assert any(
        r.levelno == logging.ERROR and "order_id=99001" in r.getMessage() and r.exc_info for r in captured.records
    )

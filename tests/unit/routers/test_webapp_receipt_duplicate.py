"""A receipt image uploaded through the Mini App can back only one manual deposit."""

from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from app.routers.webapp import balance

USER_ID = 5


def _png(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(content: bytes) -> SimpleNamespace:
    async def read() -> bytes:
        return content

    return SimpleNamespace(filename="receipt.png", content_type="image/png", read=read)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(hashes=set(), created=[], linked=[], duplicate_logs=0)
    settings = SimpleNamespace(pay_mode=True, manual_deposit_min=1, manual_deposit_max=10_000_000)

    async def authenticate_user(**kwargs: Any) -> int:
        return USER_ID

    async def get_settings(self):
        return settings

    async def read_user(self, user_id: int):
        return SimpleNamespace(id=user_id, number=None, amount=0)

    async def try_insert(self, phash: str, user_id: int):
        if phash in state.hashes:
            return None
        state.hashes.add(phash)
        return SimpleNamespace(phash=phash)

    async def update_transaction_id(self, phash: str, tx_id: int) -> bool:
        state.linked.append((phash, tx_id))
        return True

    async def create(self, user_id: int, amount: int, method: str):
        state.created.append(amount)
        return SimpleNamespace(id=len(state.created), amount=amount)

    async def stop_after_create(self, tx):
        # Everything after creating the transaction (rules, admin log) is out of scope.
        raise RuntimeError("stop")

    async def log_duplicate(*args: Any) -> None:
        state.duplicate_logs += 1

    monkeypatch.setattr(balance, "authenticate_user", authenticate_user)
    monkeypatch.setattr(balance, "_phone_verify_required", lambda settings, user: False)
    monkeypatch.setattr(balance.SettingsManager, "get_settings", get_settings)
    monkeypatch.setattr(balance.UserCRUD, "read_user", read_user)
    monkeypatch.setattr(balance.ReceiptHashCRUD, "try_insert", try_insert)
    monkeypatch.setattr(balance.ReceiptHashCRUD, "update_transaction_id", update_transaction_id)
    monkeypatch.setattr(balance.TransactionCRUD, "create", create)
    monkeypatch.setattr(balance.ManualAutoApproveRuleCRUD, "schedule_for_transaction", stop_after_create)
    monkeypatch.setattr(balance, "_log_duplicate_receipt", log_duplicate)
    return state


def _send(content: bytes):
    return asyncio.run(balance.deposit_manual_receipt(amount=1000, file=_upload(content)))


def test_same_image_twice_creates_one_transaction(env: SimpleNamespace) -> None:
    image = _png((10, 20, 30))
    _send(image)
    second = _send(image)

    assert env.created == [1000]
    assert env.duplicate_logs == 1
    assert len(env.linked) == 1
    assert second.ok is True  # the sender is not told about the duplicate


def test_different_images_each_create_a_transaction(env: SimpleNamespace) -> None:
    _send(_png((10, 20, 30)))
    _send(_png((200, 100, 50)))

    assert env.created == [1000, 1000]
    assert env.duplicate_logs == 0

"""The manual-card log caption keeps the Mini App tag when it is rebuilt on approve/reject."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.db.crud import manual_auto_approve_rules as rules


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def counts(self, user_id: int) -> dict:
        return {}

    async def get_entity(user_id: int):
        raise RuntimeError("offline")

    monkeypatch.setattr(rules.TransactionCRUD, "count_user_transactions_by_method_status", counts)
    monkeypatch.setattr(rules.Kenzo, "get_entity", get_entity)


def _caption(from_webapp: bool) -> str:
    return asyncio.run(
        rules.build_manual_card_log_caption(
            user_id=1,
            amount=1000,
            header="approved",
            reduser=SimpleNamespace(amount=0, number=None),
            from_webapp=from_webapp,
        )
    )


def test_rebuilt_webapp_caption_keeps_tag_and_is_detected_again() -> None:
    caption = _caption(True)
    assert rules.WEBAPP_RECEIPT_TAG in caption.splitlines()[0]
    # A second review edit must still see it as a Mini App receipt.
    assert rules.is_webapp_receipt_log(caption) is True


def test_bot_caption_has_no_webapp_tag() -> None:
    caption = _caption(False)
    assert rules.WEBAPP_RECEIPT_TAG not in caption
    assert rules.is_webapp_receipt_log(caption) is False


def test_tag_outside_first_line_does_not_count() -> None:
    # User-controlled fields (e.g. a name) appear below the header and must not fake the tag.
    assert rules.is_webapp_receipt_log(f"header\nname: {rules.WEBAPP_RECEIPT_TAG}") is False


def test_webapp_tag_is_english() -> None:
    assert rules.WEBAPP_RECEIPT_TAG == "#WebApp"


@pytest.mark.parametrize("text", [None, ""])
def test_empty_message_is_not_webapp(text: str | None) -> None:
    assert rules.is_webapp_receipt_log(text) is False

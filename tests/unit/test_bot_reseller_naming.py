"""How bot reseller usernames are built from the admin's prefix and suffix choices."""

from __future__ import annotations

import pytest

from app.db.models.bot_reseller import NAMING_TELEGRAM_ID, BotReseller
from app.services.bot_reseller.core import Refused, build_username, clean_affix


def _reseller(prefix: str, suffix: str = "") -> BotReseller:
    return BotReseller(id=3, telegram_id=58219034, username_prefix=prefix, username_suffix=suffix, created_at=0)


@pytest.mark.parametrize(
    ("prefix", "suffix", "expected"),
    [
        ("rb3", "", "rb3_ali"),
        ("", "", "ali"),
        (NAMING_TELEGRAM_ID, "", "58219034_ali"),
        ("", NAMING_TELEGRAM_ID, "ali_58219034"),
        ("shop", "vip", "shop_ali_vip"),
    ],
)
def test_build_username(prefix: str, suffix: str, expected: str) -> None:
    assert build_username(_reseller(prefix, suffix), "ali") == expected


@pytest.mark.parametrize("raw", ["", NAMING_TELEGRAM_ID, "Shop", " vip1 "])
def test_clean_affix_accepts(raw: str) -> None:
    assert clean_affix(raw) == raw.strip().lower()


@pytest.mark.parametrize("raw", ["a_b", "with space", "x" * 13, "{tid}"])
def test_clean_affix_refuses(raw: str) -> None:
    with pytest.raises(Refused):
        clean_affix(raw)

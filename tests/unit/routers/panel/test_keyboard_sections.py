"""Which section of the bot buttons page each keyboard key is grouped under."""

from __future__ import annotations

import pytest

from app.routers.panel.keyboard import SECTION_SLUGS, _section_of
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_TITLES


@pytest.mark.parametrize(
    ("key", "section"),
    [
        ("bt.menu_buy_service", "main_menu"),
        ("in.ms.extra_volume", "my_services"),
        ("in.balance.crypto", "balance"),
        ("in.buy.confirm", "buy"),
        ("in.rs.change_password", "reseller"),
        ("something.unknown", "other"),
    ],
)
def test_key_prefix_selects_the_section(key: str, section: str):
    assert _section_of(key) == section


def test_every_registered_button_lands_in_a_named_section():
    assert {_section_of(key) for key in KEYBOARD_BUTTON_TITLES} <= set(SECTION_SLUGS) - {"other"}

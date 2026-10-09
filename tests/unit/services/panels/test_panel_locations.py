"""Per-panel invoice locations, and admin screens that survive emoji-heavy input."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.panels import locations as locations_module
from app.services.panels.locations import fill_locations, panel_locations_mode, resolve_plan_locations
from app.services.panels.settings import LOCATION_MAX_LENGTH, LOCATIONS_MAX_ITEMS, parse_locations_value
from app.telegram.admin.panels.locations_view import (
    build_locations_view,
    build_node_prefixes_view,
    resolve_prefix_token,
)

TEMPLATE = "**▪️ حجم :** 10\n**▫️ لوکیشن های موجودسرویس :** \n**^qc^{locations}^qc^**\n**💸 قیمت :** 5"
FLAGS = "🇩🇪🇫🇮🇳🇱🇺🇸🇹🇷🇬🇧🇫🇷🇨🇦"


def _panel(**subscription) -> SimpleNamespace:
    return SimpleNamespace(code=7, name="Panel 7", subscription_settings=subscription)


def test_parse_locations_trims_dedupes_and_caps() -> None:
    raw = "🇩🇪  آلمان \n\n🇩🇪 آلمان\n🇫🇮 فنلاند، 🇳🇱 هلند\n" + "x" * 200
    parsed = parse_locations_value(raw)
    assert parsed[:3] == ["🇩🇪 آلمان", "🇫🇮 فنلاند", "🇳🇱 هلند"]
    assert all(len(item) <= LOCATION_MAX_LENGTH for item in parsed)
    assert len(parse_locations_value([f"loc {i}" for i in range(100)])) == LOCATIONS_MAX_ITEMS
    assert parse_locations_value(None) == []


def test_unknown_mode_falls_back_to_auto() -> None:
    assert panel_locations_mode(_panel(locations_mode="bogus")) == "auto"
    assert panel_locations_mode(_panel()) == "auto"


def test_fill_locations_replaces_or_strips_the_block() -> None:
    filled = fill_locations(TEMPLATE, ["🇩🇪 آلمان", "🇫🇮 فنلاند"])
    assert "🇩🇪 آلمان ⌁ 🇫🇮 فنلاند" in filled
    hidden = fill_locations(TEMPLATE, None)
    assert "{locations}" not in hidden and "لوکیشن" not in hidden
    assert hidden == "**▪️ حجم :** 10\n**💸 قیمت :** 5"


def test_resolve_follows_the_panel_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    async def nodes(panel, plan) -> list[str]:
        return ["node-a"]

    monkeypatch.setattr(locations_module, "fetch_node_locations", nodes)
    plan = SimpleNamespace()
    run = asyncio.run
    assert run(resolve_plan_locations(_panel(), plan)) == ["node-a"]
    assert run(resolve_plan_locations(_panel(locations_mode="hidden"), plan)) is None
    manual = _panel(locations_mode="manual", locations=["🇩🇪 آلمان"])
    assert run(resolve_plan_locations(manual, plan)) == ["🇩🇪 آلمان"]
    # An empty manual list never leaves the invoice blank.
    assert run(resolve_plan_locations(_panel(locations_mode="manual", locations=[]), plan)) == ["node-a"]


def _callback_data(buttons: list) -> list[bytes]:
    # This Telethon build wraps callback buttons as KeyboardInlineButton(type=...).
    return [getattr(button, "data", None) or button.type.data for row in buttons for button in row]


def test_admin_screens_keep_callback_data_short_with_flag_prefixes() -> None:
    panel = _panel(
        node_prefixes=[f"{FLAGS} long prefix {i}" for i in range(5)],
        locations_mode="manual",
        locations=[f"{FLAGS} {i}" for i in range(LOCATIONS_MAX_ITEMS)],
    )
    for builder in (build_node_prefixes_view, build_locations_view):
        _text, buttons = builder(panel)
        assert all(len(data) <= 64 for data in _callback_data(buttons))


def test_prefix_token_maps_index_and_legacy_text() -> None:
    panel = _panel(node_prefixes=["LT -", "TUN -"])
    assert resolve_prefix_token(panel, "0") == "LT -"
    assert resolve_prefix_token(panel, "3") == "TUN -"
    assert resolve_prefix_token(panel, "HYB -") == "HYB -"

"""Per-panel invoice locations, and admin screens that survive emoji-heavy input."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.db.crud.bot_texts import panel_locations_text_key
from app.services.panels import locations as locations_module
from app.services.panels.locations import (
    LocationsBlock,
    fill_locations,
    panel_locations_mode,
    resolve_plan_locations,
    validate_locations_text,
)
from app.telegram.admin.panels.locations_view import (
    build_locations_view,
    build_node_prefixes_view,
    resolve_prefix_token,
)

TEMPLATE = "**▪️ حجم :** 10\n**▫️ لوکیشن های موجودسرویس :** \n**^qc^{locations}^qc^**\n**💸 قیمت :** 5"
FLAGS = "🇩🇪🇫🇮🇳🇱🇺🇸🇹🇷🇬🇧🇫🇷🇨🇦"
ADMIN_TEXT = "🌍 **لوکیشن‌ها:**\n[🇩🇪](emoji/5222) آلمان ⌁ 🇫🇮 فنلاند"


def _panel(**subscription) -> SimpleNamespace:
    return SimpleNamespace(code=7, name="Panel 7", subscription_settings=subscription)


@pytest.fixture
def stored_texts(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    texts: dict[str, str] = {}

    async def get_text(self, key: str, lang: str | None = None) -> str | None:
        return texts.get(key)

    async def nodes(panel, plan) -> list[str]:
        return ["node-a", "node-b"]

    monkeypatch.setattr(locations_module.BotTextCRUD, "get_text", get_text)
    monkeypatch.setattr(locations_module, "fetch_node_locations", nodes)
    return texts


def test_text_key_is_per_panel() -> None:
    assert panel_locations_text_key(7) == "panel_locations_7"


def test_unknown_mode_falls_back_to_auto() -> None:
    assert panel_locations_mode(_panel(locations_mode="bogus")) == "auto"
    assert panel_locations_mode(_panel()) == "auto"


def test_validate_only_rejects_empty_or_oversized_text() -> None:
    assert validate_locations_text(ADMIN_TEXT) is None
    assert validate_locations_text("   ") is not None
    assert validate_locations_text("x" * 3001) is not None


def test_node_names_fill_only_the_placeholder() -> None:
    filled = fill_locations(TEMPLATE, LocationsBlock("node-a ⌁ node-b"))
    assert "لوکیشن های موجودسرویس" in filled
    assert "^qc^node-a ⌁ node-b^qc^" in filled


def test_admin_text_replaces_the_whole_section_verbatim() -> None:
    filled = fill_locations(TEMPLATE, LocationsBlock(ADMIN_TEXT, custom=True))
    assert filled == f"**▪️ حجم :** 10\n{ADMIN_TEXT}\n**💸 قیمت :** 5"


def test_hidden_removes_the_section() -> None:
    assert fill_locations(TEMPLATE, None) == "**▪️ حجم :** 10\n**💸 قیمت :** 5"


def test_resolve_follows_the_panel_mode(stored_texts: dict[str, str]) -> None:
    plan = SimpleNamespace()
    run = asyncio.run
    assert run(resolve_plan_locations(_panel(), plan)) == LocationsBlock("node-a ⌁ node-b")
    assert run(resolve_plan_locations(_panel(locations_mode="hidden"), plan)) is None
    # Manual without a stored text never leaves the invoice blank.
    assert run(resolve_plan_locations(_panel(locations_mode="manual"), plan)) == LocationsBlock("node-a ⌁ node-b")
    stored_texts["panel_locations_7"] = ADMIN_TEXT
    assert run(resolve_plan_locations(_panel(locations_mode="manual"), plan)) == LocationsBlock(ADMIN_TEXT, custom=True)


def test_list_saved_by_the_earlier_version_still_shows(stored_texts: dict[str, str]) -> None:
    panel = _panel(locations_mode="manual", locations=["🇩🇪 آلمان", "🇫🇮 فنلاند"])
    block = asyncio.run(resolve_plan_locations(panel, SimpleNamespace()))
    assert block == LocationsBlock("🇩🇪 آلمان\n🇫🇮 فنلاند", custom=True)


def _callback_data(buttons: list) -> list[bytes]:
    # This Telethon build wraps callback buttons as KeyboardInlineButton(type=...).
    return [getattr(button, "data", None) or button.type.data for row in buttons for button in row]


def test_admin_screens_keep_callback_data_short_with_flags(stored_texts: dict[str, str]) -> None:
    panel = _panel(node_prefixes=[f"{FLAGS} long prefix {i}" for i in range(5)], locations_mode="manual")
    stored_texts["panel_locations_7"] = f"{FLAGS}\n" * 200
    _text, prefix_buttons = build_node_prefixes_view(panel)
    text, location_buttons = asyncio.run(build_locations_view(panel))
    assert all(len(data) <= 64 for data in _callback_data(prefix_buttons + location_buttons))
    # The admin's text is shown trimmed, so the screen stays far below Telegram's limit.
    assert len(text) < 2000


def test_prefix_token_maps_index_and_legacy_text() -> None:
    panel = _panel(node_prefixes=["LT -", "TUN -"])
    assert resolve_prefix_token(panel, "0") == "LT -"
    assert resolve_prefix_token(panel, "3") == "TUN -"
    assert resolve_prefix_token(panel, "HYB -") == "HYB -"

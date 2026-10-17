"""Bot-text defaults: one registry feeds both the bot fallback and the admin editors."""

from __future__ import annotations

from types import SimpleNamespace

from app.routers.panel.texts import _entry
from app.telegram.keyboards.texts import TEXT_KEYS_CONFIG
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS, default_bot_text

# Defaults built per plan at runtime, so there is no static text to show.
RUNTIME_DEFAULT_KEYS = {
    "no_services_message_button",
    "reseller_plan_guide_fixed",
    "reseller_plan_guide_hourly",
    "reseller_plan_guide_unlimited",
    "reseller_plan_guide_usage",
}


def test_every_editable_key_has_a_default() -> None:
    keys = {item["key"] for items in TEXT_KEYS_CONFIG.values() for item in items}
    assert keys - RUNTIME_DEFAULT_KEYS <= DEFAULT_BOT_TEXTS.keys()
    assert all(value.strip() for value in DEFAULT_BOT_TEXTS.values())


def test_default_lookup() -> None:
    assert default_bot_text("help_message") == DEFAULT_BOT_TEXTS["help_message"]
    assert default_bot_text("missing_key") is None


def test_unset_entry_exposes_default() -> None:
    entry = _entry("help_message", {}, None)
    assert entry.stored is False
    assert entry.value is None
    assert entry.default_value == DEFAULT_BOT_TEXTS["help_message"]


def test_stored_entry_keeps_override() -> None:
    row = SimpleNamespace(value="custom", lang="fa", banner_url=None, banner_position=None)
    entry = _entry("help_message", {}, row)
    assert entry.stored is True
    assert entry.value == "custom"
    assert entry.default_value == DEFAULT_BOT_TEXTS["help_message"]

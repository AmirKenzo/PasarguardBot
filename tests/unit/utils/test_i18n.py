"""Locale catalogs: every language mirrors the default one and lookups fall back cleanly."""

from __future__ import annotations

import re

import pytest

from app.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    _catalog,
    lookup,
    namespace,
    normalize_language,
    t,
)
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS, default_bot_text

PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}")
FORMAT_MARKERS = ("^q^", "^qc^", "**", "`", "<b>", "</b>", "<code>", "</code>")


@pytest.mark.parametrize("lang", [code for code in SUPPORTED_LANGUAGES if code != DEFAULT_LANGUAGE])
def test_catalog_mirrors_default_language(lang: str) -> None:
    base, other = _catalog(DEFAULT_LANGUAGE), _catalog(lang)
    assert other.keys() == base.keys()
    for ns, entries in base.items():
        assert other[ns].keys() == entries.keys(), ns
        for key, text in entries.items():
            translated = other[ns][key]
            assert translated.strip(), f"{lang}:{ns}.{key} is empty"
            assert sorted(PLACEHOLDER.findall(translated)) == sorted(PLACEHOLDER.findall(text)), f"{ns}.{key}"
            for marker in FORMAT_MARKERS:
                assert translated.count(marker) == text.count(marker), f"{ns}.{key} {marker}"


def test_normalize_language() -> None:
    assert normalize_language("EN-us") == "en"
    assert normalize_language(None) == DEFAULT_LANGUAGE
    assert normalize_language("de") == DEFAULT_LANGUAGE


def test_lookup_and_fallback() -> None:
    assert lookup("buttons.bt.menu_help", "en") == "📚 Help"
    assert lookup("buttons.bt.menu_help", "de") == lookup("buttons.bt.menu_help", DEFAULT_LANGUAGE)
    assert lookup("buttons.missing", "en") is None
    assert t("buttons.missing") == "buttons.missing"


def test_t_fills_only_given_placeholders() -> None:
    text = t("bot_texts.reseller_select_plan_prompt", "en", panel_name="DE-1")
    assert "DE-1" in text
    assert "{panel_name}" not in text
    assert "{count}" in t("bot_texts.reseller_my_list_intro", "en")


def test_registries_use_default_language() -> None:
    assert namespace("bot_texts", DEFAULT_LANGUAGE).items() <= DEFAULT_BOT_TEXTS.items()
    assert namespace("buttons", DEFAULT_LANGUAGE).items() <= KEYBOARD_BUTTON_DEFAULTS.items()
    assert default_bot_text("help_message", "en") != default_bot_text("help_message")
    assert default_bot_text("help_message", "en") == lookup("bot_texts.help_message", "en")

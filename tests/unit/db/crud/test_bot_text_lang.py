"""Bot text lookups without a language resolve to the default one, and the panel list shows one row per key."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.crud.bot_texts import resolve_text_lang
from app.i18n import DEFAULT_LANGUAGE
from app.routers.panel.texts import _stored_by_key


@pytest.mark.parametrize("lang", [None, "", "  "])
def test_missing_lang_resolves_to_default(lang: str | None) -> None:
    assert resolve_text_lang(lang) == DEFAULT_LANGUAGE


def test_lang_is_trimmed_and_lowercased() -> None:
    assert resolve_text_lang(" EN ") == "en"


def _row(key: str, lang: str | None) -> SimpleNamespace:
    return SimpleNamespace(key=key, lang=lang)


def test_panel_list_prefers_default_language_row() -> None:
    en = _row("start_message", "en")
    fa = _row("start_message", DEFAULT_LANGUAGE)
    assert _stored_by_key([en, fa])["start_message"] is fa
    assert _stored_by_key([fa, en])["start_message"] is fa


def test_panel_list_keeps_key_stored_only_in_another_language() -> None:
    en = _row("help_message", "en")
    assert _stored_by_key([en]) == {"help_message": en}

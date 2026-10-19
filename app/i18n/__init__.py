"""Bot translations: one JSON catalog per language under ``app/i18n/locales``.

Catalogs are grouped by namespace (``bot_texts``, ``buttons``, ...). A key is addressed as
``"<namespace>.<name>"``; only the first dot separates the two, so button keys such as
``bt.menu_help`` stay intact (``t("buttons.bt.menu_help")``). Missing entries fall back to
``DEFAULT_LANGUAGE``, so a partial translation never shows a blank message.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from app.logger import get_logger

logger = get_logger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LANGUAGE = "fa"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("fa", "en")


def normalize_language(lang: str | None) -> str:
    """Map any language code (``en-US``, ``EN``, None) to a supported one."""
    code = (lang or "").strip().lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


@cache
def _catalog(lang: str) -> dict[str, dict[str, str]]:
    path = LOCALES_DIR / f"{lang}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error(f"Failed to load locale catalog {path.name}: {exc}")
        return {}
    return {ns: dict(entries) for ns, entries in data.items() if isinstance(entries, dict)}


def namespace(name: str, lang: str | None = None) -> dict[str, str]:
    """All entries of one namespace for ``lang``, filled in from the default language."""
    merged = dict(_catalog(DEFAULT_LANGUAGE).get(name, {}))
    code = normalize_language(lang)
    if code != DEFAULT_LANGUAGE:
        merged.update(_catalog(code).get(name, {}))
    return merged


def lookup(key: str, lang: str | None = None) -> str | None:
    """The translation for ``key`` or None when no catalog defines it."""
    ns, _, name = key.partition(".")
    code = normalize_language(lang)
    for candidate in dict.fromkeys((code, DEFAULT_LANGUAGE)):
        value = _catalog(candidate).get(ns, {}).get(name)
        if value is not None:
            return value
    return None


def t(key: str, lang: str | None = None, **placeholders: object) -> str:
    """Translate ``key``; ``{name}`` placeholders are replaced only when passed, others stay as-is."""
    text = lookup(key, lang)
    if text is None:
        logger.warning(f"Missing translation key: {key}")
        return key
    for name, value in placeholders.items():
        text = text.replace(f"{{{name}}}", str(value))
    return text


__all__ = [
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "lookup",
    "namespace",
    "normalize_language",
    "t",
]

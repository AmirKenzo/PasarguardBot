"""Theme packs: share customized bot texts, button labels and the home menu layout as one JSON file.

A pack is plain data, never code. Export picks what goes in; import is always two steps: a
preview that validates every entry against this bot and compares it with what is stored, then
an apply of the entries the admin ticked. Apply writes everything in one transaction together
with a snapshot of the rows it replaced, so the last import can be undone.

Pack layout (version 1)::

    {
        "format": "kenzo-theme-pack",
        "version": 1,
        "name": "...",
        "source": {"bot": "pasarguard", "app_version": "...", "created_at": 1700000000},
        "texts": {"<key>": {"<lang>": {"value": "...", "banner_url": null, "banner_position": null}}},
        "buttons": {"<key>": {"text": "...", "style": "primary", "icon": "5895443668663275064"}},
        "layout": {"rows": [["bt.menu_my_services", "bt.menu_buy_service"], ...], "hidden": [...]},
    }

Optional fields are written only when they carry something: a missing ``banner_url``, ``style``
or ``icon`` leaves the receiver's value alone, an explicit ``null`` banner removes theirs.
Emoji ids travel as strings because they do not fit in a JavaScript number.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any

from sqlalchemy import select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.keyboards import invalidate_keyboard_button_cache
from app.db.models.bot_text import BotText
from app.db.models.keyboards import KeyboardButton
from app.db.models.theme_pack import ThemePack, ThemePackImport
from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from app.logger import get_logger
from app.models.panel.keyboard import OTHER_SECTION, SECTION_PREFIXES, STYLE_OPTIONS
from app.models.panel.texts import BANNER_POSITIONS
from app.telegram.keyboards.home import HOME_BUTTON_KEYS, current_home_layout
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS, KEYBOARD_BUTTON_TITLES
from app.telegram.keyboards.texts import TEXT_KEYS_CONFIG, TEXT_SECTIONS
from app.utils.text.default_texts import default_bot_text
from app.utils.text.glass import GLASS_STYLE, glass_text, unglass_text
from app.version import VERSIONS

log = get_logger(__name__)

PACK_FORMAT = "kenzo-theme-pack"
PACK_VERSION = 1
SOURCE_BOT = "pasarguard"
PACK_FILE_SUFFIX = ".kenzopack.json"

MAX_PACK_BYTES = 1_000_000
MAX_ENTRIES = 1000
MAX_NAME_LENGTH = 100
MAX_TEXT_LENGTH = 8192
MAX_BUTTON_TEXT_LENGTH = 100
MAX_BANNER_URL_LENGTH = 500
KEEP_IMPORTS = 10

# Texts tied to this bot's own panels; they mean nothing on another bot.
PRIVATE_TEXT_PREFIXES = ("panel_locations_",)
OTHER_TEXT_SECTION = "other"

PACK_STYLES = tuple(style for style in STYLE_OPTIONS if style)  # "none" = no colour at all
TELEGRAM_HTML_TAGS = frozenset(
    {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre"}
    | {"blockquote", "tg-emoji"}
)

KIND_TEXT = "text"
KIND_BUTTON = "button"
KIND_LAYOUT = "layout"
LAYOUT_ID = "layout"

STATUS_NEW = "new"
STATUS_CHANGED = "changed"
STATUS_SAME = "same"
STATUS_INVALID = "invalid"
STATUS_UNKNOWN = "unknown"
APPLICABLE = (STATUS_NEW, STATUS_CHANGED)


class PackError(ValueError):
    """The file is not a usable pack at all; ``code`` says why."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def text_catalog() -> dict[str, dict[str, Any]]:
    """Every text key this bot can store, with its admin title, section and placeholders."""
    catalog: dict[str, dict[str, Any]] = {}
    for section, items in TEXT_KEYS_CONFIG.items():
        for item in items:
            catalog[item["key"]] = {
                "title": item.get("title") or item["key"],
                "section": section,
                "placeholders": dict(item.get("placeholders") or {}),
            }
    return catalog


def text_sections() -> list[dict[str, str]]:
    sections = [
        {"key": key, "name": meta.get("name", key), "icon": meta.get("icon", "")} for key, meta in TEXT_SECTIONS.items()
    ]
    if OTHER_TEXT_SECTION not in TEXT_SECTIONS:
        sections.append({"key": OTHER_TEXT_SECTION, "name": "", "icon": ""})
    return sections


def is_private_text(key: str) -> bool:
    return key.startswith(PRIVATE_TEXT_PREFIXES)


def known_button_keys() -> set[str]:
    return set(KEYBOARD_BUTTON_TITLES) | set(KEYBOARD_BUTTON_DEFAULTS) | set(HOME_BUTTON_KEYS)


def button_section(key: str) -> str:
    for prefix, slug in SECTION_PREFIXES:
        if key.startswith(prefix):
            return slug
    return OTHER_SECTION


def button_customized(row: KeyboardButton | None) -> bool:
    """True when the stored row changes the label, the colour or the icon of the button."""
    if row is None:
        return False
    text = unglass_text(row.button_text or "")
    default = KEYBOARD_BUTTON_DEFAULTS.get(row.button_key)
    custom_text = bool(text) and (default is None or row.button_text != default)
    return custom_text or row.button_style is not None or row.button_icon is not None


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("card_number", re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")),
    ("phone", re.compile(r"(?<!\d)(?:\+98|0098|0)9\d{9}(?!\d)")),
    ("link", re.compile(r"(?:https?://|(?<![\w.])t\.me/|telegram\.me/)\S+", re.IGNORECASE)),
    ("username", re.compile(r"(?<![\w@/])@[A-Za-z][A-Za-z0-9_]{3,31}")),
)
_PLACEHOLDER = re.compile(r"(?<!\{)\{([A-Za-z_][\w.]*)(?:[!:][^{}]*)?\}(?!\})")
_HTML_TAG = re.compile(r"</?[A-Za-z][\w-]*[^>]*>")
_ICON = re.compile(r"\d{1,19}")


def sensitive_hints(text: str | None) -> list[str]:
    """Kinds of personal data a text seems to carry (usernames, links, card or phone numbers)."""
    if not text:
        return []
    normalized = text.translate(_DIGITS)
    return [code for code, pattern in _SENSITIVE_PATTERNS if pattern.search(normalized)]


def placeholders_of(text: str | None) -> set[str]:
    return set(_PLACEHOLDER.findall(text or ""))


def allowed_placeholders(key: str) -> set[str]:
    """Placeholders the bot fills for ``key``: its documented ones plus those in its defaults."""
    names = set(text_catalog().get(key, {}).get("placeholders", {}))
    for lang in SUPPORTED_LANGUAGES:
        names |= placeholders_of(default_bot_text(key, lang))
    return names


class _TagBalance(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.broken = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in TELEGRAM_HTML_TAGS:
            self.broken = True
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            self.broken = True
            return
        self.stack.pop()


def html_is_broken(text: str) -> bool:
    """True when Telegram would reject the text as HTML: unknown tags or unbalanced ones."""
    parser = _TagBalance()
    parser.feed(text)
    parser.close()
    return parser.broken or bool(parser.stack)


def _uses_html(key: str) -> bool:
    return any(_HTML_TAG.search(default_bot_text(key, lang) or "") for lang in SUPPORTED_LANGUAGES)


def check_text(key: str, value: str) -> tuple[list[str], list[str]]:
    """(warnings, errors) for an incoming text value."""
    warnings: list[str] = []
    errors: list[str] = []
    if not value.strip():
        errors.append("empty")
    if len(value) > MAX_TEXT_LENGTH:
        errors.append("too_long")
    allowed = allowed_placeholders(key)
    found = placeholders_of(value)
    # The bot fills most texts with str.format, so an unknown placeholder would crash the handler.
    if found - allowed:
        errors.append("unknown_placeholders")
    if allowed - found:
        warnings.append("missing_placeholders")
    if _uses_html(key) and html_is_broken(value):
        errors.append("broken_html")
    warnings.extend(f"sensitive_{code}" for code in sensitive_hints(value))
    return warnings, errors


@dataclass
class PackItem:
    """One importable entry: a text in one language, a button, or the home layout."""

    id: str
    kind: str
    key: str
    lang: str | None = None
    title: str = ""
    section: str = ""
    status: str = STATUS_NEW
    current: str | None = None
    incoming: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        out = asdict(self)
        out.pop("data")
        return out


@dataclass
class ParsedPack:
    name: str
    source: dict[str, Any]
    items: list[PackItem]


def text_item_id(key: str, lang: str) -> str:
    return f"{KIND_TEXT}:{key}:{lang}"


def button_item_id(key: str) -> str:
    return f"{KIND_BUTTON}:{key}"


def _clean_str(value: Any, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, str | int | float) else ""


def parse_pack(raw: Any) -> ParsedPack:
    """Validate a pack's shape and every entry in it. Raises PackError when the file is unusable."""
    if not isinstance(raw, dict):
        raise PackError("not_a_pack")
    if raw.get("format") != PACK_FORMAT:
        raise PackError("not_a_pack")
    version = raw.get("version")
    if not isinstance(version, int) or version < 1:
        raise PackError("not_a_pack")
    if version > PACK_VERSION:
        raise PackError("newer_version")
    if len(json.dumps(raw, ensure_ascii=False).encode("utf-8")) > MAX_PACK_BYTES:
        raise PackError("too_large")

    texts = raw.get("texts") or {}
    buttons = raw.get("buttons") or {}
    layout = raw.get("layout")
    if not isinstance(texts, dict) or not isinstance(buttons, dict) or not (layout is None or isinstance(layout, dict)):
        raise PackError("not_a_pack")
    entry_count = sum(len(langs) if isinstance(langs, dict) else 1 for langs in texts.values()) + len(buttons)
    if entry_count > MAX_ENTRIES:
        raise PackError("too_many_entries")

    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    items = [*_parse_texts(texts), *_parse_buttons(buttons)]
    if layout is not None:
        items.append(_parse_layout(layout))
    if not items:
        raise PackError("empty")
    return ParsedPack(
        name=_clean_str(raw.get("name"), MAX_NAME_LENGTH),
        source={
            "bot": _clean_str(source.get("bot"), 40),
            "app_version": _clean_str(source.get("app_version"), 40),
            "created_at": source.get("created_at") if isinstance(source.get("created_at"), int) else None,
        },
        items=items,
    )


def _parse_texts(texts: dict[str, Any]) -> list[PackItem]:
    catalog = text_catalog()
    items: list[PackItem] = []
    for raw_key, langs in texts.items():
        key = str(raw_key)[:100]
        meta = catalog.get(key)
        known = (meta is not None or default_bot_text(key) is not None) and not is_private_text(key)
        title = (meta or {}).get("title") or key
        section = (meta or {}).get("section") or OTHER_TEXT_SECTION
        if not isinstance(langs, dict):
            items.append(
                PackItem(
                    text_item_id(key, "?"), KIND_TEXT, key, None, title, section, STATUS_INVALID, errors=["malformed"]
                )
            )
            continue
        for raw_lang, entry in langs.items():
            lang = str(raw_lang).strip().lower()[:10]
            item = PackItem(text_item_id(key, lang), KIND_TEXT, key, lang, title, section)
            items.append(item)
            if not known:
                item.status = STATUS_UNKNOWN
                continue
            if lang not in SUPPORTED_LANGUAGES:
                item.status, item.errors = STATUS_INVALID, ["unsupported_language"]
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("value"), str):
                item.status, item.errors = STATUS_INVALID, ["malformed"]
                continue
            value = entry["value"]
            item.incoming = value
            item.warnings, item.errors = check_text(key, value)
            item.data = {"value": value, "has_banner": "banner_url" in entry}
            if "banner_url" in entry:
                url = entry.get("banner_url")
                position = entry.get("banner_position") or ""
                if url is not None and (
                    not isinstance(url, str) or not url.startswith("https://") or len(url) > MAX_BANNER_URL_LENGTH
                ):
                    item.errors.append("bad_banner")
                if position not in BANNER_POSITIONS:
                    item.errors.append("bad_banner")
                item.data["banner_url"] = url or None
                item.data["banner_position"] = position or None
                if url:
                    item.warnings.append("has_banner")
            if item.errors:
                item.status = STATUS_INVALID
    return items


def _parse_buttons(buttons: dict[str, Any]) -> list[PackItem]:
    known = known_button_keys()
    items: list[PackItem] = []
    for raw_key, entry in buttons.items():
        key = str(raw_key)[:100]
        item = PackItem(
            button_item_id(key), KIND_BUTTON, key, None, KEYBOARD_BUTTON_TITLES.get(key, key), button_section(key)
        )
        items.append(item)
        if key not in known:
            item.status = STATUS_UNKNOWN
            continue
        if not isinstance(entry, dict) or not ({"text", "style", "icon"} & entry.keys()):
            item.status, item.errors = STATUS_INVALID, ["malformed"]
            continue
        data: dict[str, Any] = {}
        if "text" in entry:
            text = entry["text"]
            if not isinstance(text, str) or not unglass_text(text).strip():
                item.errors.append("empty")
            elif len(unglass_text(text)) > MAX_BUTTON_TEXT_LENGTH:
                item.errors.append("too_long")
            else:
                data["text"] = text
                item.warnings.extend(f"sensitive_{code}" for code in sensitive_hints(text))
        if "style" in entry:
            style = entry["style"]
            if style not in PACK_STYLES:
                item.errors.append("bad_style")
            else:
                data["style"] = style
        if "icon" in entry:
            icon = entry["icon"]
            icon_text = str(icon) if isinstance(icon, str | int) and not isinstance(icon, bool) else ""
            if not _ICON.fullmatch(icon_text) or int(icon_text) >= 2**63:
                item.errors.append("bad_icon")
            else:
                data["icon"] = int(icon_text)
                item.warnings.append("premium_icon")
        if data.get("style") and "text" in data:
            label = unglass_text(data["text"])
            data["text"] = glass_text(label) if data["style"] == GLASS_STYLE else label
        item.data = data
        item.incoming = data.get("text")
        if item.errors:
            item.status = STATUS_INVALID
    return items


def _parse_layout(layout: dict[str, Any]) -> PackItem:
    item = PackItem(LAYOUT_ID, KIND_LAYOUT, LAYOUT_ID)
    rows = layout.get("rows")
    hidden = layout.get("hidden") or []
    if not isinstance(rows, list) or not isinstance(hidden, list):
        item.status, item.errors = STATUS_INVALID, ["malformed"]
        return item
    allowed = set(HOME_BUTTON_KEYS)
    placed: set[str] = set()
    clean_rows: list[list[str]] = []
    dropped = False
    for row in rows:
        if not isinstance(row, list):
            dropped = True
            continue
        keys = []
        for key in row:
            if isinstance(key, str) and key in allowed and key not in placed:
                keys.append(key)
                placed.add(key)
            else:
                dropped = True
        if keys:
            clean_rows.append(keys)
    if not clean_rows:
        item.status, item.errors = STATUS_INVALID, ["empty"]
        return item
    if dropped:
        item.warnings.append("unknown_buttons_dropped")
    item.data = {"rows": clean_rows, "hidden": sorted({key for key in hidden if key in placed})}
    item.incoming = _layout_summary(clean_rows, item.data["hidden"])
    return item


def _layout_summary(rows: list[list[str]], hidden: list[str]) -> str:
    hidden_set = set(hidden)
    return "\n".join(
        " | ".join(f"{KEYBOARD_BUTTON_TITLES.get(key, key)}{' (hidden)' if key in hidden_set else ''}" for key in row)
        for row in rows
    )


async def _load_state(
    text_keys: set[str] | None = None,
) -> tuple[dict[tuple[str, str], BotText], dict[str, KeyboardButton]]:
    async with Session() as session:
        stmt = select(BotText)
        if text_keys is not None:
            stmt = stmt.where(BotText.key.in_(text_keys or {""}))
        texts = {(row.key, row.lang): row for row in (await session.execute(stmt)).scalars()}
        buttons = {row.button_key: row for row in (await session.execute(select(KeyboardButton))).scalars()}
    return texts, buttons


def _current_layout(buttons: dict[str, KeyboardButton]) -> tuple[list[list[str]], list[str], bool]:
    """(rows, hidden home keys, whether the admin changed the layout at all)."""
    placement = {key: (row.sort_row, row.sort_order or 0) for key, row in buttons.items() if row.sort_row is not None}
    hidden = sorted(key for key in HOME_BUTTON_KEYS if key in buttons and buttons[key].hidden)
    return current_home_layout(placement), hidden, bool(placement or hidden)


async def inventory() -> dict[str, Any]:
    """Everything that could go into a pack, with what is customized and what looks personal."""
    texts, buttons = await _load_state()
    catalog = text_catalog()
    stored_by_key: dict[str, list[BotText]] = {}
    for (key, _lang), row in texts.items():
        if not is_private_text(key):
            stored_by_key.setdefault(key, []).append(row)

    text_entries = []
    for key in [*catalog, *sorted(k for k in stored_by_key if k not in catalog)]:
        meta = catalog.get(key, {})
        rows = sorted(stored_by_key.get(key, []), key=lambda r: r.lang)
        hints = sorted({hint for row in rows for hint in sensitive_hints(row.value)})
        text_entries.append(
            {
                "key": key,
                "title": meta.get("title") or key,
                "section": meta.get("section") or OTHER_TEXT_SECTION,
                "langs": [row.lang for row in rows],
                "has_default": default_bot_text(key) is not None,
                "has_banner": any(row.banner_url for row in rows),
                "hints": hints,
            }
        )

    button_entries = []
    for key in sorted(known_button_keys() | set(buttons)):
        row = buttons.get(key)
        button_entries.append(
            {
                "key": key,
                "title": KEYBOARD_BUTTON_TITLES.get(key, key),
                "section": button_section(key),
                "customized": button_customized(row),
                "has_icon": bool(row and row.button_icon),
                "hints": sensitive_hints(row.button_text) if row else [],
            }
        )

    _rows, _hidden, layout_customized = _current_layout(buttons)
    return {
        "texts": text_entries,
        "buttons": button_entries,
        "text_sections": text_sections(),
        "button_sections": [slug for _prefix, slug in SECTION_PREFIXES] + [OTHER_SECTION],
        "layout_customized": layout_customized,
        "last_import": await last_import(),
    }


async def build_pack(
    *,
    name: str = "",
    text_keys: list[str] | tuple[str, ...] = (),
    button_keys: list[str] | tuple[str, ...] = (),
    include_layout: bool = False,
    include_banners: bool = True,
    include_icons: bool = True,
    include_defaults: bool = False,
) -> dict[str, Any]:
    """Build a pack from the selected keys. Keys this bot does not know are skipped."""
    wanted_texts = {key for key in text_keys if not is_private_text(key)}
    texts_state, buttons_state = await _load_state(wanted_texts)

    texts: dict[str, dict[str, dict[str, Any]]] = {}
    for key in sorted(wanted_texts):
        rows = sorted((row for (k, _l), row in texts_state.items() if k == key), key=lambda r: r.lang)
        entries: dict[str, dict[str, Any]] = {}
        for row in rows:
            entry: dict[str, Any] = {"value": row.value}
            if include_banners:
                entry["banner_url"] = row.banner_url or None
                entry["banner_position"] = row.banner_position or None
            entries[row.lang] = entry
        if not entries and include_defaults and (default := default_bot_text(key)) is not None:
            entries[DEFAULT_LANGUAGE] = {"value": default}
        if entries:
            texts[key] = entries

    known = known_button_keys()
    buttons: dict[str, dict[str, Any]] = {}
    for key in sorted(set(button_keys) & known):
        row = buttons_state.get(key)
        entry = {}
        if row is not None and button_customized(row):
            if row.button_text:
                entry["text"] = row.button_text
            if row.button_style is not None:
                entry["style"] = row.button_style or "none"
            if include_icons and row.button_icon:
                entry["icon"] = str(row.button_icon)
        elif include_defaults and key in KEYBOARD_BUTTON_DEFAULTS:
            entry["text"] = KEYBOARD_BUTTON_DEFAULTS[key]
        if entry:
            buttons[key] = entry

    pack: dict[str, Any] = {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "name": name.strip()[:MAX_NAME_LENGTH],
        "source": {"bot": SOURCE_BOT, "app_version": VERSIONS.app, "created_at": int(time.time())},
        "texts": texts,
        "buttons": buttons,
    }
    if include_layout:
        rows, hidden, _customized = _current_layout(buttons_state)
        pack["layout"] = {"rows": rows, "hidden": hidden}
    return pack


def pack_counts(pack: dict[str, Any]) -> dict[str, int]:
    return {
        "texts": sum(len(langs) for langs in (pack.get("texts") or {}).values()),
        "buttons": len(pack.get("buttons") or {}),
        "layout": 1 if pack.get("layout") else 0,
    }


def pack_file_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-").lower()[:40]
    return f"{slug or 'theme'}-{time.strftime('%Y%m%d')}{PACK_FILE_SUFFIX}"


def pack_to_json(pack: dict[str, Any]) -> str:
    return json.dumps(pack, ensure_ascii=False, indent=2)


def _button_snapshot(row: KeyboardButton | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"button_text": row.button_text, "button_style": row.button_style, "button_icon": row.button_icon}


def _button_matches(row: KeyboardButton | None, data: dict[str, Any]) -> bool:
    if row is None:
        return False
    if "text" in data and row.button_text != data["text"]:
        return False
    if "style" in data and row.button_style != ("" if data["style"] == "none" else data["style"]):
        return False
    return not ("icon" in data and row.button_icon != data["icon"])


async def preview(raw: Any) -> ParsedPack:
    """Parse ``raw`` and mark every entry new, changed or the same as what this bot stores."""
    parsed = parse_pack(raw)
    keys = {item.key for item in parsed.items if item.kind == KIND_TEXT}
    texts, buttons = await _load_state(keys)
    for item in parsed.items:
        if item.kind == KIND_TEXT and item.lang:
            row = texts.get((item.key, item.lang))
            item.current = row.value if row else default_bot_text(item.key, item.lang)
            if item.status in (STATUS_INVALID, STATUS_UNKNOWN):
                continue
            if row is None:
                item.status = STATUS_NEW
            else:
                same_banner = not item.data["has_banner"] or (
                    (row.banner_url or None) == item.data.get("banner_url")
                    and (row.banner_position or None) == item.data.get("banner_position")
                )
                item.status = STATUS_SAME if row.value == item.data["value"] and same_banner else STATUS_CHANGED
        elif item.kind == KIND_BUTTON:
            row = buttons.get(item.key)
            item.current = (row.button_text if row and row.button_text else None) or KEYBOARD_BUTTON_DEFAULTS.get(
                item.key
            )
            if item.status in (STATUS_INVALID, STATUS_UNKNOWN):
                continue
            if _button_matches(row, item.data):
                item.status = STATUS_SAME
            else:
                item.status = STATUS_CHANGED if button_customized(row) else STATUS_NEW
        elif item.kind == KIND_LAYOUT:
            rows, hidden, customized = _current_layout(buttons)
            item.current = _layout_summary(rows, hidden)
            if item.status == STATUS_INVALID:
                continue
            if rows == item.data["rows"] and hidden == item.data["hidden"]:
                item.status = STATUS_SAME
            else:
                item.status = STATUS_CHANGED if customized else STATUS_NEW
    return parsed


MODE_MERGE = "merge"
MODE_REPLACE = "replace"
APPLY_MODES = (MODE_MERGE, MODE_REPLACE)


@dataclass
class ApplyResult:
    applied: int
    texts: int
    buttons: int
    layout: bool
    reset: int
    import_id: int | None


def _text_snapshot(row: BotText | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"value": row.value, "banner_url": row.banner_url, "banner_position": row.banner_position}


async def apply(
    raw: Any,
    item_ids: list[str] | None,
    *,
    actor_id: int | None,
    mode: str = MODE_MERGE,
    pack_id: int | None = None,
) -> ApplyResult:
    """Write the ticked entries in one transaction and keep a snapshot of what they replaced.

    ``item_ids=None`` applies every entry that differs from the bot (a one-click switch).
    ``mode="replace"`` also resets every text and button the pack does not mention back to the
    built-in default, so switching from one pack to another leaves nothing of the first behind.
    The pack is parsed and compared again here, so a crafted request can only apply entries
    that pass the same checks the preview showed.
    """
    parsed = await preview(raw)
    wanted = None if item_ids is None else set(item_ids)
    chosen = [item for item in parsed.items if (wanted is None or item.id in wanted) and item.status in APPLICABLE]
    replace = mode == MODE_REPLACE
    if not chosen and not replace:
        return ApplyResult(0, 0, 0, False, 0, None)

    text_items = [item for item in chosen if item.kind == KIND_TEXT]
    button_items = [item for item in chosen if item.kind == KIND_BUTTON]
    layout_item = next((item for item in chosen if item.kind == KIND_LAYOUT), None)
    # Everything the pack mentions stays as it is in replace mode, ticked or not.
    pack_texts = {(item.key, item.lang) for item in parsed.items if item.kind == KIND_TEXT}
    pack_buttons = {item.key for item in parsed.items if item.kind == KIND_BUTTON}
    backup: dict[str, Any] = {"texts": [], "buttons": [], "created_buttons": [], "layout": None}
    reset = 0

    async with Session() as session:
        if replace:
            text_rows = {(row.key, row.lang): row for row in (await session.execute(select(BotText))).scalars()}
        else:
            text_keys = {item.key for item in text_items} or {""}
            text_rows = {
                (row.key, row.lang): row
                for row in (await session.execute(select(BotText).where(BotText.key.in_(text_keys)))).scalars()
            }
        button_rows = {row.button_key: row for row in (await session.execute(select(KeyboardButton))).scalars()}

        if replace:
            for (key, lang), row in list(text_rows.items()):
                if (key, lang) in pack_texts or is_private_text(key):
                    continue
                backup["texts"].append({"key": key, "lang": lang, "row": _text_snapshot(row)})
                await session.delete(row)
                reset += 1
            for key, row in button_rows.items():
                if key in pack_buttons or not button_customized(row):
                    continue
                backup["buttons"].append({"key": key, "row": _button_snapshot(row)})
                row.button_text, row.button_style, row.button_icon = "", None, None
                reset += 1

        for item in text_items:
            row = text_rows.get((item.key, item.lang))
            backup["texts"].append({"key": item.key, "lang": item.lang, "row": _text_snapshot(row)})
            if row is None:
                row = BotText(key=item.key, lang=item.lang, value=item.data["value"])
                session.add(row)
            row.value = item.data["value"]
            if item.data["has_banner"]:
                row.banner_url = item.data.get("banner_url")
                row.banner_position = item.data.get("banner_position")

        if layout_item is not None:
            backup["layout"] = {
                key: [row.sort_row, row.sort_order, bool(row.hidden)] for key, row in button_rows.items()
            }

        def ensure_button(key: str) -> KeyboardButton:
            row = button_rows.get(key)
            if row is None:
                row = KeyboardButton(button_key=key, button_text="", hidden=False)
                session.add(row)
                button_rows[key] = row
                backup["created_buttons"].append(key)
            return row

        for item in button_items:
            if item.key not in backup["created_buttons"]:
                backup["buttons"].append({"key": item.key, "row": _button_snapshot(button_rows.get(item.key))})
            row = ensure_button(item.key)
            if "text" in item.data:
                row.button_text = item.data["text"]
            if "style" in item.data:
                row.button_style = "" if item.data["style"] == "none" else item.data["style"]
            if "icon" in item.data:
                row.button_icon = item.data["icon"]

        if layout_item is not None:
            placement = {
                key: (row_index, position)
                for row_index, keys in enumerate(layout_item.data["rows"])
                for position, key in enumerate(keys)
            }
            hidden = set(layout_item.data["hidden"])
            for key in placement:
                ensure_button(key)
            for key, row in button_rows.items():
                spot = placement.get(key)
                row.sort_row = spot[0] if spot else None
                row.sort_order = spot[1] if spot else None
                if key in placement:
                    row.hidden = key in hidden

        record = ThemePackImport(
            pack_id=pack_id,
            actor_id=actor_id,
            pack_name=parsed.name or None,
            mode=MODE_REPLACE if replace else MODE_MERGE,
            summary=json.dumps(
                {
                    "texts": len(text_items),
                    "buttons": len(button_items),
                    "layout": layout_item is not None,
                    "reset": reset,
                }
            ),
            backup=json.dumps(backup, ensure_ascii=False),
            created_at=int(time.time()),
        )
        session.add(record)
        await session.commit()
        import_id = record.id

    invalidate_keyboard_button_cache()
    await _prune_imports()
    return ApplyResult(len(chosen), len(text_items), len(button_items), layout_item is not None, reset, import_id)


async def _prune_imports() -> None:
    try:
        async with Session() as session:
            rows = (
                await session.execute(select(ThemePackImport).order_by(ThemePackImport.id.desc()).offset(KEEP_IMPORTS))
            ).scalars()
            for row in rows:
                await session.delete(row)
            await session.commit()
    except Exception as exc:
        log.warning("theme pack: could not prune old imports: %s", exc)


async def last_import() -> dict[str, Any] | None:
    async with Session() as session:
        row = (
            (await session.execute(select(ThemePackImport).order_by(ThemePackImport.id.desc()).limit(1)))
            .scalars()
            .first()
        )
    if row is None:
        return None
    try:
        summary = json.loads(row.summary or "{}")
    except ValueError:
        summary = {}
    return {
        "id": row.id,
        "pack_name": row.pack_name or "",
        "created_at": row.created_at,
        "restored": row.restored_at is not None,
        "pack_id": row.pack_id,
        "mode": row.mode,
        "summary": summary,
    }


async def undo_last_import() -> int | None:
    """Put back what the newest import replaced. Returns its id, or None when there is nothing to undo."""
    async with Session() as session:
        record = (
            (await session.execute(select(ThemePackImport).order_by(ThemePackImport.id.desc()).limit(1)))
            .scalars()
            .first()
        )
        if record is None or record.restored_at is not None:
            return None
        backup = json.loads(record.backup)

        for entry in backup.get("texts", []):
            row = (
                (
                    await session.execute(
                        select(BotText).where(BotText.key == entry["key"], BotText.lang == entry["lang"])
                    )
                )
                .scalars()
                .first()
            )
            old = entry.get("row")
            if old is None:
                if row is not None:
                    await session.delete(row)
                continue
            if row is None:
                row = BotText(key=entry["key"], lang=entry["lang"], value=old["value"])
                session.add(row)
            row.value = old["value"]
            row.banner_url = old.get("banner_url")
            row.banner_position = old.get("banner_position")

        button_rows = {row.button_key: row for row in (await session.execute(select(KeyboardButton))).scalars()}
        for entry in backup.get("buttons", []):
            row, old = button_rows.get(entry["key"]), entry.get("row")
            if row is not None and old is not None:
                row.button_text = old["button_text"]
                row.button_style = old["button_style"]
                row.button_icon = old["button_icon"]
        layout = backup.get("layout")
        if layout is not None:
            for key, row in button_rows.items():
                if key in layout:
                    row.sort_row, row.sort_order, row.hidden = layout[key][0], layout[key][1], bool(layout[key][2])
        for key in backup.get("created_buttons", []):
            if key in button_rows:
                await session.delete(button_rows[key])

        record.restored_at = int(time.time())
        await session.commit()
        record_id = record.id

    invalidate_keyboard_button_cache()
    return record_id


MAX_LIBRARY_PACKS = 50
DEFAULT_PACK_NAME = "Theme pack"


def pack_from_items(parsed: ParsedPack, *, name: str | None = None) -> dict[str, Any]:
    """Rebuild a clean pack from its valid entries; invalid and unknown ones are left out."""
    texts: dict[str, dict[str, dict[str, Any]]] = {}
    buttons: dict[str, dict[str, Any]] = {}
    layout: dict[str, Any] | None = None
    for item in parsed.items:
        if item.status in (STATUS_INVALID, STATUS_UNKNOWN) or not item.data:
            continue
        if item.kind == KIND_TEXT and item.lang:
            entry: dict[str, Any] = {"value": item.data["value"]}
            if item.data["has_banner"]:
                entry["banner_url"] = item.data.get("banner_url")
                entry["banner_position"] = item.data.get("banner_position")
            texts.setdefault(item.key, {})[item.lang] = entry
        elif item.kind == KIND_BUTTON:
            entry = {name_: item.data[name_] for name_ in ("text", "style") if name_ in item.data}
            if "icon" in item.data:
                entry["icon"] = str(item.data["icon"])
            buttons[item.key] = entry
        elif item.kind == KIND_LAYOUT:
            layout = {"rows": item.data["rows"], "hidden": item.data["hidden"]}
    pack: dict[str, Any] = {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "name": (name if name is not None else parsed.name).strip()[:MAX_NAME_LENGTH],
        "source": {
            "bot": parsed.source.get("bot") or SOURCE_BOT,
            "app_version": parsed.source.get("app_version") or VERSIONS.app,
            "created_at": parsed.source.get("created_at") or int(time.time()),
        },
        "texts": texts,
        "buttons": buttons,
    }
    if layout is not None:
        pack["layout"] = layout
    return pack


def _load_data(row: ThemePack) -> dict[str, Any]:
    try:
        data = json.loads(row.data)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _library_entry(row: ThemePack, active_id: int | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "source_bot": row.source_bot or "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "counts": pack_counts(_load_data(row)),
        "active": row.id == active_id,
    }


async def active_pack_id() -> int | None:
    """Library pack applied last, unless that apply was undone."""
    async with Session() as session:
        row = (
            (await session.execute(select(ThemePackImport).order_by(ThemePackImport.id.desc()).limit(1)))
            .scalars()
            .first()
        )
    if row is None or row.restored_at is not None:
        return None
    return row.pack_id


async def list_packs() -> list[dict[str, Any]]:
    active_id = await active_pack_id()
    async with Session() as session:
        rows = (await session.execute(select(ThemePack).order_by(ThemePack.updated_at.desc()))).scalars().all()
    return [_library_entry(row, active_id) for row in rows]


async def get_pack(pack_id: int) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(library entry, pack data) of one saved pack."""
    async with Session() as session:
        row = await session.get(ThemePack, pack_id)
    if row is None:
        return None
    return _library_entry(row, await active_pack_id()), _load_data(row)


@dataclass
class SaveResult:
    pack_id: int | None
    dropped: list[PackItem]
    error: str | None = None


async def save_pack(
    raw: Any,
    *,
    pack_id: int | None = None,
    name: str = "",
    actor_id: int | None = None,
    strict: bool = False,
) -> SaveResult:
    """Store a pack in the library, as a new one or over ``pack_id``.

    ``strict`` refuses to save while any entry is invalid (the editor shows them); otherwise
    invalid and unknown entries are dropped and reported (a file from another bot or version).
    Raises PackError when the data is not a usable pack.
    """
    parsed = parse_pack(raw)
    dropped = [item for item in parsed.items if item.status in (STATUS_INVALID, STATUS_UNKNOWN)]
    if strict and dropped:
        return SaveResult(None, dropped, "invalid_entries")
    clean_name = (name or parsed.name or DEFAULT_PACK_NAME).strip()[:MAX_NAME_LENGTH]
    pack = pack_from_items(parsed, name=clean_name)
    if not (pack["texts"] or pack["buttons"] or pack.get("layout")):
        raise PackError("empty")
    now = int(time.time())
    async with Session() as session:
        if pack_id is None:
            count = len((await session.execute(select(ThemePack.id))).scalars().all())
            if count >= MAX_LIBRARY_PACKS:
                return SaveResult(None, dropped, "library_full")
            row = ThemePack(created_by=actor_id, created_at=now, name=clean_name, data="", updated_at=now)
            session.add(row)
        else:
            row = await session.get(ThemePack, pack_id)
            if row is None:
                return SaveResult(None, dropped, "not_found")
        row.name = clean_name
        row.data = pack_to_json(pack)
        row.source_bot = pack["source"]["bot"][:40]
        row.updated_at = now
        await session.commit()
        saved_id = row.id
    return SaveResult(saved_id, dropped)


async def delete_pack(pack_id: int) -> bool:
    async with Session() as session:
        row = await session.get(ThemePack, pack_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
    return True


ERROR_TEXTS = {
    "not_a_pack": "این فایل یک پک ظاهری معتبر نیست.",
    "newer_version": "این پک با نسخهٔ جدیدتری از ربات ساخته شده؛ اول ربات را به‌روز کنید.",
    "too_large": "حجم پک بیشتر از حد مجاز (۱ مگابایت) است.",
    "too_many_entries": "تعداد موارد این پک بیشتر از حد مجاز است.",
    "empty": "این پک هیچ مورد قابل استفاده‌ای ندارد.",
    "library_full": f"کتابخانه پر است (حداکثر {MAX_LIBRARY_PACKS} پک)؛ اول یک پک را حذف کنید.",
    "not_found": "پک پیدا نشد.",
    "invalid_entries": "بعضی موارد این پک نامعتبرند؛ اول آن‌ها را درست کنید.",
    "no_source": "پک یا فایل پک مشخص نشده است.",
    "bad_mode": "حالت اعمال نامعتبر است.",
}


def error_text(code: str) -> str:
    """Persian message for a PackError / SaveResult error code."""
    return ERROR_TEXTS.get(code, "اجرای این عملیات با خطا روبه‌رو شد.")


def share_caption(entry: dict[str, Any]) -> str:
    """Plain-text caption for a pack file sent to Telegram so it can be forwarded."""
    counts = entry.get("counts") or {}
    return (
        f"🎨 پک ظاهری «{entry.get('name', '')}»\n"
        f"📝 متن‌ها: {counts.get('texts', 0)} · 🔘 دکمه‌ها: {counts.get('buttons', 0)}"
        f"{' · 🧩 چیدمان منو' if counts.get('layout') else ''}\n\n"
        "برای استفاده، این فایل را در پنل مدیریت ← پک‌های ظاهری ← «وارد کردن فایل» بارگذاری کنید."
    )

"""Web app color themes: the admin's custom theme library, the active theme, and its share format.

Built-in presets ship with the frontend (``frontend/src/design/webappThemes.ts``). The backend
stores only custom themes plus a snapshot of whichever theme is active, so the public endpoint
can serve it to every user without knowing the presets.

Theme layout::

    {"radius": 16, "light": {palette}, "dark": {palette}}

where a palette holds one ``#rrggbb`` color per ``PALETTE_KEYS`` entry and a ``border_alpha``.

A shared theme travels as a theme pack that carries only the web app section::

    {"format": "kenzo-theme-pack", "version": 1, "name": "...", "source": {...}, "webapp": {theme}}
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from sqlalchemy import func, select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.settings import SettingsManager
from app.db.models.webapp_theme import WebappTheme
from app.logger import get_logger
from app.services.theme_pack import PACK_FORMAT, PACK_VERSION, SOURCE_BOT
from app.version import VERSIONS

log = get_logger(__name__)

PALETTE_KEYS = (
    "bg",
    "surface",
    "surface_2",
    "text",
    "text_muted",
    "primary",
    "primary_strong",
    "primary_text",
    "accent",
    "success",
    "warning",
    "danger",
)
SCHEMES = ("light", "dark")
MIN_RADIUS = 4
MAX_RADIUS = 26
DEFAULT_RADIUS = 16
MAX_BORDER_ALPHA = 0.35
DEFAULT_BORDER_ALPHA = {"light": 0.11, "dark": 0.12}
MAX_NAME_LENGTH = 100
MAX_LIBRARY_THEMES = 50
DEFAULT_THEME_NAME = "Theme"
SHARE_FILE_SUFFIX = ".kenzotheme.json"

MODE_TELEGRAM = "telegram"
MODE_CUSTOM = "custom"
MODES = (MODE_TELEGRAM, MODE_CUSTOM)
DEFAULT_ACTIVE = "default"
CUSTOM_PREFIX = "custom:"
_PRESET_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_HEX = re.compile(r"^#[0-9a-f]{6}$")

ERROR_TEXTS = {
    "bad_theme": "رنگ‌های این تم کامل یا معتبر نیستند.",
    "not_found": "این تم پیدا نشد.",
    "library_full": f"کتابخانه پر است؛ حداکثر {MAX_LIBRARY_THEMES} تم سفارشی می‌توانید داشته باشید.",
    "bad_active": "شناسهٔ تم معتبر نیست.",
    "bad_mode": "حالت رنگ وب‌اپ معتبر نیست.",
}


class ThemeError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def error_text(code: str) -> str:
    return ERROR_TEXTS.get(code, "عملیات انجام نشد.")


def custom_id(theme_id: int) -> str:
    return f"{CUSTOM_PREFIX}{theme_id}"


def parse_custom_id(active: str) -> int | None:
    if not active.startswith(CUSTOM_PREFIX):
        return None
    tail = active[len(CUSTOM_PREFIX) :]
    return int(tail) if tail.isdigit() else None


def _palette(raw: Any, scheme: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ThemeError("bad_theme")
    palette: dict[str, Any] = {}
    for key in PALETTE_KEYS:
        value = raw.get(key)
        if not isinstance(value, str) or not _HEX.match(value.strip().lower()):
            raise ThemeError("bad_theme")
        palette[key] = value.strip().lower()
    alpha = raw.get("border_alpha", DEFAULT_BORDER_ALPHA[scheme])
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise ThemeError("bad_theme")
    palette["border_alpha"] = round(min(max(float(alpha), 0.0), MAX_BORDER_ALPHA), 3)
    return palette


def normalize_theme(raw: Any) -> dict[str, Any]:
    """Validate a theme and return it in canonical form. Raises ThemeError("bad_theme")."""
    if not isinstance(raw, dict):
        raise ThemeError("bad_theme")
    radius = raw.get("radius", DEFAULT_RADIUS)
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise ThemeError("bad_theme")
    theme: dict[str, Any] = {"radius": int(min(max(round(radius), MIN_RADIUS), MAX_RADIUS))}
    for scheme in SCHEMES:
        theme[scheme] = _palette(raw.get(scheme), scheme)
    return theme


def _load(row: WebappTheme) -> dict[str, Any] | None:
    try:
        return normalize_theme(json.loads(row.data))
    except ValueError, ThemeError:
        log.warning("webapp theme %s has unreadable data", row.id)
        return None


def _entry(row: WebappTheme, theme: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "source_bot": row.source_bot or "",
        "imported": bool(row.imported),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "theme": theme,
    }


async def list_themes() -> list[dict[str, Any]]:
    async with Session() as session:
        rows = (await session.execute(select(WebappTheme).order_by(WebappTheme.created_at))).scalars().all()
    entries = []
    for row in rows:
        theme = _load(row)
        if theme is not None:
            entries.append(_entry(row, theme))
    return entries


async def get_theme(theme_id: int) -> dict[str, Any] | None:
    async with Session() as session:
        row = await session.get(WebappTheme, theme_id)
    if row is None:
        return None
    theme = _load(row)
    return _entry(row, theme) if theme is not None else None


async def save_theme(
    raw: Any,
    *,
    name: str,
    theme_id: int | None = None,
    actor_id: int | None = None,
    source_bot: str = "",
    imported: bool = False,
) -> int:
    """Store a theme as a new library entry or over ``theme_id``. Raises ThemeError."""
    theme = normalize_theme(raw)
    clean_name = (name or "").strip()[:MAX_NAME_LENGTH] or DEFAULT_THEME_NAME
    now = int(time.time())
    async with Session() as session:
        if theme_id is None:
            count = (await session.execute(select(func.count(WebappTheme.id)))).scalar_one()
            if count >= MAX_LIBRARY_THEMES:
                raise ThemeError("library_full")
            row = WebappTheme(
                created_by=actor_id,
                created_at=now,
                source_bot=(source_bot or "").strip()[:40] or None,
                imported=imported,
                name=clean_name,
                data="",
                updated_at=now,
            )
            session.add(row)
        else:
            row = await session.get(WebappTheme, theme_id)
            if row is None:
                raise ThemeError("not_found")
        row.name = clean_name
        row.data = json.dumps(theme, ensure_ascii=False)
        row.updated_at = now
        await session.commit()
        saved_id = row.id

    config = await get_config()
    if config["active"] == custom_id(saved_id):
        await _write(webapp_theme_snapshot=theme)
    return saved_id


async def delete_theme(theme_id: int) -> bool:
    async with Session() as session:
        row = await session.get(WebappTheme, theme_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
    config = await get_config()
    if config["active"] == custom_id(theme_id):
        await _write(webapp_theme_active=DEFAULT_ACTIVE, webapp_theme_snapshot=None)
    return True


async def _write(**updates: Any) -> None:
    updates["webapp_theme_version"] = int(time.time() * 1000)
    manager = SettingsManager()
    setting = await manager.get_settings()
    if setting is None:
        await manager.add_setting(**updates)
    else:
        await manager.update_setting(setting.id, **updates)


async def get_config() -> dict[str, Any]:
    setting = await SettingsManager().get_settings()

    def read(key: str, default: Any) -> Any:
        if setting is None:
            return default
        value = getattr(setting, key, default)
        return default if value is None and default is not None else value

    mode = read("webapp_theme_mode", MODE_TELEGRAM)
    snapshot = read("webapp_theme_snapshot", None)
    try:
        snapshot = normalize_theme(snapshot) if snapshot is not None else None
    except ThemeError:
        snapshot = None
    return {
        "mode": mode if mode in MODES else MODE_TELEGRAM,
        "active": str(read("webapp_theme_active", DEFAULT_ACTIVE) or DEFAULT_ACTIVE),
        "snapshot": snapshot,
        "user_scheme": bool(read("webapp_theme_user_scheme", True)),
        "user_pick": bool(read("webapp_theme_user_pick", False)),
        "version": int(read("webapp_theme_version", 0) or 0),
    }


async def update_options(
    *, mode: str | None = None, user_scheme: bool | None = None, user_pick: bool | None = None
) -> None:
    updates: dict[str, Any] = {}
    if mode is not None:
        if mode not in MODES:
            raise ThemeError("bad_mode")
        updates["webapp_theme_mode"] = mode
    if user_scheme is not None:
        updates["webapp_theme_user_scheme"] = user_scheme
    if user_pick is not None:
        updates["webapp_theme_user_pick"] = user_pick
    if updates:
        await _write(**updates)


async def activate(active: str, snapshot: Any = None) -> dict[str, Any]:
    """Make a theme the one every user sees and switch to custom mode.

    A custom theme is read from the library; a preset is identified by id and its palette
    comes from the caller (the frontend owns the presets). Returns the stored snapshot.
    """
    theme_id = parse_custom_id(active)
    if theme_id is not None:
        entry = await get_theme(theme_id)
        if entry is None:
            raise ThemeError("not_found")
        theme = entry["theme"]
    elif active.startswith(CUSTOM_PREFIX) or not _PRESET_ID.match(active):
        raise ThemeError("bad_active")
    else:
        theme = normalize_theme(snapshot)
    await _write(webapp_theme_mode=MODE_CUSTOM, webapp_theme_active=active, webapp_theme_snapshot=theme)
    return theme


async def public_config() -> dict[str, Any]:
    """What every web app user gets: the mode, the active theme and the themes they may pick from."""
    config = await get_config()
    choices: list[dict[str, Any]] = []
    if config["user_pick"]:
        choices = [
            {"id": custom_id(entry["id"]), "name": entry["name"], "theme": entry["theme"]}
            for entry in await list_themes()
        ]
    return {
        "mode": config["mode"],
        "active": config["active"],
        "theme": config["snapshot"],
        "user_scheme": config["user_scheme"],
        "user_pick": config["user_pick"],
        "version": config["version"],
        "choices": choices,
    }


def share_pack(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "name": entry["name"],
        "source": {"bot": SOURCE_BOT, "app_version": VERSIONS.app, "created_at": int(time.time())},
        "webapp": entry["theme"],
    }


def share_file_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-").lower()[:40]
    return f"{slug or 'webapp-theme'}{SHARE_FILE_SUFFIX}"


def share_caption(entry: dict[str, Any]) -> str:
    """Plain-text caption for a theme file sent to Telegram so it can be forwarded."""
    return (
        f"🎨 تم رنگی وب‌اپ «{entry.get('name', '')}»\n\n"
        "برای استفاده، این فایل را در پنل مدیریت ← تم‌پک‌ها ← رنگ وب‌اپ ← «وارد کردن» بارگذاری کنید."
    )

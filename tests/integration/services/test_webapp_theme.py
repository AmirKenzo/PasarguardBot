"""Web app color themes: validation, the custom library, activation and the public config."""

from __future__ import annotations

import asyncio
import copy

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.crud import settings as settings_crud
from app.db.models.settings import Settings
from app.db.models.webapp_theme import WebappTheme
from app.services import webapp_theme as wt
from app.services.theme_pack import PackError, parse_pack

TABLES = [Settings.__table__, WebappTheme.__table__]

PALETTE = {
    "bg": "#F4F5F9",
    "surface": "#ffffff",
    "surface_2": "#eef0f6",
    "text": "#10131c",
    "text_muted": "#6b7280",
    "primary": "#3b82f6",
    "primary_strong": "#2563eb",
    "primary_text": "#ffffff",
    "accent": "#06b6d4",
    "success": "#16a34a",
    "warning": "#d97706",
    "danger": "#dc2626",
    "border_alpha": 0.11,
}
THEME = {"radius": 16, "light": PALETTE, "dark": {**PALETTE, "bg": "#0a0c14", "border_alpha": 0.12}}


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'themes.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(WebappTheme.metadata.create_all, tables=TABLES)
        return async_sessionmaker(engine, expire_on_commit=False)

    session = asyncio.run(setup())
    monkeypatch.setattr(wt, "Session", session)
    monkeypatch.setattr(settings_crud, "Session", session)
    settings_crud.invalidate_settings_cache()
    yield session
    settings_crud.invalidate_settings_cache()
    asyncio.run(engine.dispose())


def run(coro):
    return asyncio.run(coro)


def test_normalize_lowercases_and_clamps() -> None:
    raw = copy.deepcopy(THEME)
    raw["radius"] = 99
    raw["light"]["border_alpha"] = 5
    theme = wt.normalize_theme(raw)
    assert theme["radius"] == wt.MAX_RADIUS
    assert theme["light"]["bg"] == "#f4f5f9"
    assert theme["light"]["border_alpha"] == wt.MAX_BORDER_ALPHA


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t["light"].pop("primary"),
        lambda t: t["dark"].update(text="red"),
        lambda t: t["dark"].update(text="#12345"),
        lambda t: t.update(radius="big"),
        lambda t: t.update(light=None),
        lambda t: t["light"].update(border_alpha=True),
    ],
)
def test_normalize_rejects_bad_themes(mutate) -> None:
    raw = copy.deepcopy(THEME)
    mutate(raw)
    with pytest.raises(wt.ThemeError):
        wt.normalize_theme(raw)


def test_defaults_follow_telegram(db) -> None:
    config = run(wt.public_config())
    assert config["mode"] == wt.MODE_TELEGRAM
    assert config["theme"] is None
    assert config["user_scheme"] is True
    assert config["choices"] == []


def test_save_list_and_delete(db) -> None:
    theme_id = run(wt.save_theme(THEME, name="  Ocean  ", source_bot="marzban", imported=True))
    entries = run(wt.list_themes())
    assert [(e["id"], e["name"], e["source_bot"], e["imported"]) for e in entries] == [
        (theme_id, "Ocean", "marzban", True)
    ]
    assert run(wt.delete_theme(theme_id)) is True
    assert run(wt.delete_theme(theme_id)) is False
    assert run(wt.list_themes()) == []


def test_activate_preset_requires_palette(db) -> None:
    with pytest.raises(wt.ThemeError):
        run(wt.activate("emerald", None))
    with pytest.raises(wt.ThemeError) as exc:
        run(wt.activate("../bad", THEME))
    assert exc.value.code == "bad_active"
    run(wt.activate("emerald", THEME))
    config = run(wt.public_config())
    assert config["mode"] == wt.MODE_CUSTOM
    assert config["active"] == "emerald"
    assert config["theme"]["light"]["bg"] == "#f4f5f9"
    assert config["version"] > 0


def test_custom_theme_snapshot_follows_edits_and_delete(db) -> None:
    theme_id = run(wt.save_theme(THEME, name="Mine"))
    run(wt.activate(wt.custom_id(theme_id)))
    edited = copy.deepcopy(THEME)
    edited["light"]["primary"] = "#ff0000"
    run(wt.save_theme(edited, name="Mine", theme_id=theme_id))
    assert run(wt.public_config())["theme"]["light"]["primary"] == "#ff0000"

    run(wt.delete_theme(theme_id))
    config = run(wt.public_config())
    assert config["active"] == wt.DEFAULT_ACTIVE
    assert config["theme"] is None


def test_activate_missing_custom_theme(db) -> None:
    with pytest.raises(wt.ThemeError) as exc:
        run(wt.activate(wt.custom_id(404)))
    assert exc.value.code == "not_found"


def test_options_and_user_choices(db) -> None:
    run(wt.save_theme(THEME, name="Pickable"))
    run(wt.update_options(mode=wt.MODE_CUSTOM, user_scheme=False, user_pick=True))
    config = run(wt.public_config())
    assert config["user_scheme"] is False
    assert [choice["name"] for choice in config["choices"]] == ["Pickable"]
    with pytest.raises(wt.ThemeError):
        run(wt.update_options(mode="neon"))


def test_library_limit(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wt, "MAX_LIBRARY_THEMES", 1)
    run(wt.save_theme(THEME, name="One"))
    with pytest.raises(wt.ThemeError) as exc:
        run(wt.save_theme(THEME, name="Two"))
    assert exc.value.code == "library_full"


def test_share_pack_is_a_theme_pack_the_text_importer_redirects() -> None:
    entry = {"name": "Ocean Blue!", "theme": wt.normalize_theme(THEME)}
    pack = wt.share_pack(entry)
    assert pack["format"] == "kenzo-theme-pack"
    assert pack["webapp"]["radius"] == 16
    assert wt.share_file_name("Ocean Blue!") == "ocean-blue.kenzotheme.json"
    with pytest.raises(PackError) as exc:
        parse_pack(pack)
    assert exc.value.code == "webapp_only"

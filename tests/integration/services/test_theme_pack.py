"""Theme packs: build from the bot, validate, preview, apply (merge/replace), undo, and the library."""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.crud import keyboards as keyboards_crud
from app.db.models.bot_text import BotText
from app.db.models.keyboards import KeyboardButton
from app.db.models.theme_pack import ThemePack, ThemePackImport
from app.services import theme_pack as tp
from app.telegram.keyboards.home import HOME_BUTTON_KEYS
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS
from app.utils.text.glass import glass_text

TABLES = [BotText.__table__, KeyboardButton.__table__, ThemePack.__table__, ThemePackImport.__table__]


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'packs.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(BotText.metadata.create_all, tables=TABLES)
        return async_sessionmaker(engine, expire_on_commit=False)

    session = asyncio.run(setup())
    monkeypatch.setattr(tp, "Session", session)
    monkeypatch.setattr(keyboards_crud, "Session", session)
    keyboards_crud.invalidate_keyboard_button_cache()
    yield session
    keyboards_crud.invalidate_keyboard_button_cache()
    asyncio.run(engine.dispose())


def run(coro):
    return asyncio.run(coro)


async def _seed(session, *, texts=(), buttons=()) -> None:
    async with session() as s:
        for key, lang, value in texts:
            s.add(BotText(key=key, lang=lang, value=value))
        for key, text, style, icon in buttons:
            s.add(KeyboardButton(button_key=key, button_text=text, button_style=style, button_icon=icon, hidden=False))
        await s.commit()


async def _texts(session) -> dict[tuple[str, str], str]:
    async with session() as s:
        return {(r.key, r.lang): r.value for r in (await s.execute(select(BotText))).scalars()}


async def _buttons(session) -> dict[str, tuple]:
    async with session() as s:
        rows = (await s.execute(select(KeyboardButton))).scalars()
        return {r.button_key: (r.button_text, r.button_style, r.button_icon, r.sort_row, r.hidden) for r in rows}


def _pack(**parts) -> dict:
    return {"format": tp.PACK_FORMAT, "version": 1, "name": "test", **parts}


# --- parsing and checks ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ([], "not_a_pack"),
        ({"format": "other", "version": 1}, "not_a_pack"),
        ({"format": tp.PACK_FORMAT, "version": 99}, "newer_version"),
        (_pack(), "empty"),
        (_pack(texts={"help_message": {"fa": {"value": "x" * 1_100_000}}}), "too_large"),
    ],
)
def test_unusable_packs_are_refused(raw, code: str) -> None:
    with pytest.raises(tp.PackError) as exc:
        tp.parse_pack(raw)
    assert exc.value.code == code


def test_entry_checks() -> None:
    parsed = tp.parse_pack(
        _pack(
            texts={
                "help_message": {"fa": {"value": "سلام {oops}"}, "de": {"value": "hallo"}},
                "webhook_notification_low_data": {
                    "fa": {"value": "<b>{remaining_volume} {service_code} {config_name}"}
                },
                "panel_locations_3": {"fa": {"value": "private"}},
                "support_message": {"fa": {"value": "پیام به @SomeAdmin یا 6037-9911-1111-2222"}},
                "no_such_key": {"fa": {"value": "x"}},
            },
            buttons={
                "bt.menu_help": {"text": "x" * 101},
                "bt.menu_profile": {"style": "rainbow"},
                "bt.menu_support": {"icon": "12ab"},
                "bt.menu_uptime": {"text": "ok", "icon": 5895443668663275064},
            },
        )
    )
    by_id = {item.id: item for item in parsed.items}
    assert by_id["text:help_message:fa"].errors == ["unknown_placeholders"]
    assert by_id["text:help_message:de"].errors == ["unsupported_language"]
    assert "broken_html" in by_id["text:webhook_notification_low_data:fa"].errors
    assert by_id["text:panel_locations_3:fa"].status == tp.STATUS_UNKNOWN
    assert by_id["text:no_such_key:fa"].status == tp.STATUS_UNKNOWN
    support = by_id["text:support_message:fa"]
    assert support.status == tp.STATUS_NEW
    assert {"sensitive_username", "sensitive_card_number"} <= set(support.warnings)
    assert by_id["button:bt.menu_help"].errors == ["too_long"]
    assert by_id["button:bt.menu_profile"].errors == ["bad_style"]
    assert by_id["button:bt.menu_support"].errors == ["bad_icon"]
    assert by_id["button:bt.menu_uptime"].data == {"text": "ok", "icon": 5895443668663275064}


def test_sensitive_hints_read_persian_digits() -> None:
    assert tp.sensitive_hints("شماره ۰۹۱۲۱۲۳۴۵۶۷") == ["phone"]
    assert tp.sensitive_hints("https://t.me/x") == ["link"]
    assert tp.sensitive_hints("hello") == []


# --- build, preview, apply, undo --------------------------------------------------------


def test_build_pack_exports_only_what_is_asked(db) -> None:
    run(
        _seed(
            db,
            texts=[("help_message", "fa", "راهنما"), ("help_message", "en", "Help!"), ("panel_locations_1", "fa", "x")],
            buttons=[("bt.menu_help", "📚 کمک", "success", 5895443668663275064), ("bt.menu_profile", "", None, None)],
        )
    )
    pack = run(
        tp.build_pack(
            name="Blue",
            text_keys=["help_message", "panel_locations_1", "support_message"],
            button_keys=["bt.menu_help", "bt.menu_profile", "nope"],
        )
    )
    assert pack["texts"] == {"help_message": {"en": {"value": "Help!"}, "fa": {"value": "راهنما"}}}
    assert pack["buttons"] == {"bt.menu_help": {"text": "📚 کمک", "style": "success", "icon": "5895443668663275064"}}
    assert "layout" not in pack
    with_defaults = run(tp.build_pack(text_keys=["support_message"], include_defaults=True, include_layout=True))
    assert with_defaults["texts"]["support_message"]["fa"]["value"] == DEFAULT_BOT_TEXTS["support_message"]
    assert [key for row in with_defaults["layout"]["rows"] for key in row] == list(HOME_BUTTON_KEYS)


def test_preview_apply_and_undo_merge(db) -> None:
    run(_seed(db, texts=[("help_message", "fa", "قدیمی"), ("start_message", "fa", "خوش آمدید")]))
    pack = _pack(
        texts={"help_message": {"fa": {"value": "جدید"}}, "start_message": {"fa": {"value": "خوش آمدید"}}},
        buttons={"bt.menu_help": {"text": "Help", "style": "glass"}},
        layout={"rows": [["bt.menu_help", "bt.menu_profile"], ["ghost"]], "hidden": ["bt.menu_profile"]},
    )
    statuses = {item.id: item.status for item in run(tp.preview(pack)).items}
    assert statuses == {
        "text:help_message:fa": "changed",
        "text:start_message:fa": "same",
        "button:bt.menu_help": "new",
        "layout": "new",
    }

    result = run(tp.apply(pack, None, actor_id=1))
    assert (result.texts, result.buttons, result.layout) == (1, 1, True)
    texts, buttons = run(_texts(db)), run(_buttons(db))
    assert texts[("help_message", "fa")] == "جدید"
    assert buttons["bt.menu_help"][:2] == (glass_text("Help"), "glass")
    assert buttons["bt.menu_help"][3] == 0
    assert buttons["bt.menu_profile"][3:] == (0, True)

    assert run(tp.undo_last_import()) == result.import_id
    assert run(_texts(db)) == {("help_message", "fa"): "قدیمی", ("start_message", "fa"): "خوش آمدید"}
    assert run(_buttons(db)) == {}
    assert run(tp.undo_last_import()) is None


def test_apply_only_ticked_entries(db) -> None:
    pack = _pack(texts={"help_message": {"fa": {"value": "a"}}, "support_message": {"fa": {"value": "b"}}})
    result = run(tp.apply(pack, ["text:support_message:fa", "text:help_message:xx"], actor_id=None))
    assert result.applied == 1
    assert run(_texts(db)) == {("support_message", "fa"): "b"}


def test_replace_mode_resets_what_the_pack_leaves_out(db) -> None:
    run(
        _seed(
            db,
            texts=[
                ("help_message", "fa", "mine"),
                ("start_message", "en", "mine too"),
                ("panel_locations_2", "fa", "x"),
            ],
            buttons=[("bt.menu_profile", "👤 me", "danger", None), ("bt.menu_support", "", None, None)],
        )
    )
    pack = _pack(texts={"support_message": {"fa": {"value": "from pack"}}}, buttons={"bt.menu_help": {"text": "H"}})
    result = run(tp.apply(pack, None, actor_id=1, mode=tp.MODE_REPLACE))
    assert result.reset == 3
    assert run(_texts(db)) == {("support_message", "fa"): "from pack", ("panel_locations_2", "fa"): "x"}
    assert run(_buttons(db))["bt.menu_profile"][:3] == ("", None, None)

    run(tp.undo_last_import())
    texts = run(_texts(db))
    assert texts == {
        ("help_message", "fa"): "mine",
        ("start_message", "en"): "mine too",
        ("panel_locations_2", "fa"): "x",
    }
    assert run(_buttons(db))["bt.menu_profile"][:3] == ("👤 me", "danger", None)
    assert "bt.menu_help" not in run(_buttons(db))


def test_banner_fields_from_older_packs_are_ignored(db) -> None:
    async def seed_banner():
        async with db() as s:
            s.add(BotText(key="start_message", lang="fa", value="old", banner_url="https://old", banner_position="top"))
            await s.commit()

    run(seed_banner())
    pack = _pack(texts={"start_message": {"fa": {"value": "new", "banner_url": "http://x", "banner_position": "?"}}})
    items = run(tp.preview(pack)).items
    assert [(item.status, item.errors, item.warnings) for item in items] == [("changed", [], [])]
    run(tp.apply(pack, None, actor_id=None))

    async def stored():
        async with db() as s:
            row = (await s.execute(select(BotText))).scalars().one()
            return row.value, row.banner_url, row.banner_position

    assert run(stored()) == ("new", "https://old", "top")
    assert "banner_url" not in json.dumps(run(tp.build_pack(text_keys=["start_message"])))


# --- library --------------------------------------------------------------------------


def test_library_save_list_edit_delete_and_active(db) -> None:
    pack = _pack(
        texts={"help_message": {"fa": {"value": "ok"}}, "unknown_key": {"fa": {"value": "x"}}},
        buttons={"bt.menu_help": {"style": "nope"}},
    )
    saved = run(tp.save_pack(pack, name="From file"))
    assert saved.error is None
    assert sorted(item.id for item in saved.dropped) == ["button:bt.menu_help", "text:unknown_key:fa"]
    entry, data = run(tp.get_pack(saved.pack_id))
    assert entry["name"] == "From file"
    assert data["texts"] == {"help_message": {"fa": {"value": "ok"}}}
    assert data["buttons"] == {}
    assert data["source"]["bot"] == tp.SOURCE_BOT

    strict = run(tp.save_pack(pack, pack_id=saved.pack_id, strict=True))
    assert strict.error == "invalid_entries"
    edited = dict(data, texts={"help_message": {"fa": {"value": "edited"}}})
    assert run(tp.save_pack(edited, pack_id=saved.pack_id, name="Renamed", strict=True)).error is None
    entry, data = run(tp.get_pack(saved.pack_id))
    assert (entry["name"], data["texts"]["help_message"]["fa"]["value"]) == ("Renamed", "edited")

    run(tp.apply(data, None, actor_id=1, pack_id=saved.pack_id))
    assert [p["active"] for p in run(tp.list_packs())] == [True]
    run(tp.undo_last_import())
    assert [p["active"] for p in run(tp.list_packs())] == [False]

    assert run(tp.delete_pack(saved.pack_id)) is True
    assert run(tp.list_packs()) == []
    assert run(tp.get_pack(saved.pack_id)) is None


def test_exported_pack_round_trips_through_json(db) -> None:
    run(_seed(db, texts=[("help_message", "fa", "x")], buttons=[("bt.menu_help", "H", None, 5895443668663275064)]))
    pack = run(tp.build_pack(text_keys=["help_message"], button_keys=["bt.menu_help"], include_layout=True))
    again = json.loads(tp.pack_to_json(pack))
    statuses = {item.status for item in run(tp.preview(again)).items}
    assert statuses == {"same"}

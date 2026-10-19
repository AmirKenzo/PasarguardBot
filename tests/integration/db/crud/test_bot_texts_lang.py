"""Bot texts keep one override per (key, lang); calls without a language use the default one."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.crud import bot_texts
from app.db.models.bot_text import BotText
from app.i18n import DEFAULT_LANGUAGE

KEY = "start_message"


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    # SQLite only autoincrements an INTEGER primary key, like MySQL does for BIGINT.
    return "INTEGER"


@pytest.fixture
def crud(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'texts.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(BotText.metadata.create_all, tables=[BotText.__table__])
        return async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(bot_texts, "Session", asyncio.run(setup()))
    yield bot_texts.BotTextCRUD()
    asyncio.run(engine.dispose())


async def _rows() -> list[tuple[str, str | None, str]]:
    async with bot_texts.Session() as session:
        result = await session.execute(select(BotText).order_by(BotText.lang))
        return [(row.key, row.lang, row.value) for row in result.scalars()]


def test_fa_and_en_overrides_of_one_key_coexist(crud: bot_texts.BotTextCRUD) -> None:
    async def run():
        assert await crud.set_text(KEY, "salam", lang="fa")
        assert await crud.set_text(KEY, "hello", lang="en")
        assert await crud.set_text(KEY, "hello again", lang="en")
        return await _rows(), await crud.get_text(KEY, "fa"), await crud.get_text(KEY, "en")

    rows, fa, en = asyncio.run(run())
    assert rows == [(KEY, "en", "hello again"), (KEY, "fa", "salam")]
    assert (fa, en) == ("salam", "hello again")


def test_lang_less_calls_use_default_language(crud: bot_texts.BotTextCRUD) -> None:
    async def run():
        assert await crud.set_text(KEY, "hello", lang="en")
        missing = await crud.get_text(KEY)
        assert await crud.set_text(KEY, "salam")
        found = await crud.get_text(KEY), (await crud.get_bot_text(KEY)).lang
        assert await crud.set_banner(KEY, "https://example.com/b.png", "top")
        banner = (await crud.get_bot_text(KEY, DEFAULT_LANGUAGE)).banner_url
        assert await crud.delete_text(KEY)
        return missing, found, banner, await _rows()

    missing, found, banner, rows = asyncio.run(run())
    # An English-only override is not served to lang-less callers.
    assert missing is None
    assert found == ("salam", DEFAULT_LANGUAGE)
    assert banner == "https://example.com/b.png"
    assert rows == [(KEY, "en", "hello")]


def test_delete_only_removes_requested_language(crud: bot_texts.BotTextCRUD) -> None:
    async def run():
        await crud.set_text(KEY, "salam", lang="fa")
        await crud.set_text(KEY, "hello", lang="en")
        assert await crud.delete_text(KEY, "en")
        assert not await crud.delete_text(KEY, "en")
        return await _rows()

    assert asyncio.run(run()) == [(KEY, "fa", "salam")]


def test_save_racing_another_insert_updates_that_row(crud: bot_texts.BotTextCRUD, monkeypatch) -> None:
    real = bot_texts._by_key
    calls = []

    def by_key(key: str, lang: str | None):
        # The first lookup misses, as if another save inserted the row right after it.
        calls.append(key)
        return real("missing" if len(calls) == 1 else key, lang)

    async def run():
        await crud.set_text(KEY, "first", lang="fa")
        monkeypatch.setattr(bot_texts, "_by_key", by_key)
        assert await crud.set_text(KEY, "second", lang="fa")
        return await _rows()

    assert asyncio.run(run()) == [(KEY, "fa", "second")]
    assert len(calls) == 2

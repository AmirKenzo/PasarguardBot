from sqlalchemy import Select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.bot_text import BotText
from app.i18n import DEFAULT_LANGUAGE


def panel_locations_text_key(panel_code: int) -> str:
    """Key of a panel's hand-written invoice locations (see services/panels/locations.py)."""
    return f"panel_locations_{int(panel_code)}"


def resolve_text_lang(lang: str | None) -> str:
    """Language a text row is stored under; calls without one mean the default language."""
    code = (lang or "").strip().lower()[:10]
    return code or DEFAULT_LANGUAGE


def _by_key(key: str, lang: str | None) -> Select[tuple[BotText]]:
    return select(BotText).where(BotText.key == key, BotText.lang == resolve_text_lang(lang))


class BotTextCRUD:
    async def get_text(self, key: str, lang: str | None = None) -> str | None:
        try:
            async with Session() as session:
                stmt = _by_key(key, lang)
                result = await session.execute(stmt)
                row = result.scalars().first()
                return row.value if row else None
        except SQLAlchemyError:
            return None

    async def get_bot_text(self, key: str, lang: str | None = None) -> BotText | None:
        """Get the full BotText object including banner fields"""
        try:
            async with Session() as session:
                stmt = _by_key(key, lang)
                result = await session.execute(stmt)
                return result.scalars().first()
        except SQLAlchemyError:
            return None

    async def set_text(
        self,
        key: str,
        value: str,
        lang: str | None = None,
        banner_url: str | None = None,
        banner_position: str | None = None,
    ) -> bool:
        for _ in range(2):
            try:
                async with Session() as session:
                    stmt = _by_key(key, lang)
                    result = await session.execute(stmt)
                    existing = result.scalars().first()
                    if existing:
                        existing.value = value
                        if banner_url is not None:
                            existing.banner_url = banner_url
                        if banner_position is not None:
                            existing.banner_position = banner_position
                    else:
                        session.add(
                            BotText(
                                key=key,
                                value=value,
                                lang=resolve_text_lang(lang),
                                banner_url=banner_url,
                                banner_position=banner_position,
                            )
                        )
                    await session.commit()
                    return True
            except IntegrityError:
                continue
            except SQLAlchemyError:
                return False
        return False

    async def set_banner(
        self, key: str, banner_url: str | None, banner_position: str | None, lang: str | None = None
    ) -> bool:
        """Set banner URL and position for a bot text"""
        try:
            async with Session() as session:
                stmt = _by_key(key, lang)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    existing.banner_url = banner_url
                    existing.banner_position = banner_position
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError:
            return False

    async def get_all(self) -> list[BotText]:
        try:
            async with Session() as session:
                result = await session.execute(select(BotText))
                return list(result.scalars().all())
        except SQLAlchemyError:
            return []

    async def delete_text(self, key: str, lang: str | None = None) -> bool:
        """Delete a text entry (reset to default)"""
        try:
            async with Session() as session:
                stmt = _by_key(key, lang)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    await session.delete(existing)
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError:
            return False

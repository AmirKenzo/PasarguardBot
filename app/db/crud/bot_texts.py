from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.bot_text import BotText


def panel_locations_text_key(panel_code: int) -> str:
    """Key of a panel's hand-written invoice locations (see services/panels/locations.py)."""
    return f"panel_locations_{int(panel_code)}"


class BotTextCRUD:
    async def get_text(self, key: str, lang: str | None = None) -> str | None:
        try:
            async with Session() as session:
                stmt = select(BotText).where(BotText.key == key)
                if lang:
                    stmt = stmt.where(BotText.lang == lang)
                result = await session.execute(stmt)
                row = result.scalars().first()
                return row.value if row else None
        except SQLAlchemyError:
            return None

    async def get_bot_text(self, key: str, lang: str | None = None) -> BotText | None:
        """Get the full BotText object including banner fields"""
        try:
            async with Session() as session:
                stmt = select(BotText).where(BotText.key == key)
                if lang:
                    stmt = stmt.where(BotText.lang == lang)
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
        try:
            async with Session() as session:
                stmt = select(BotText).where(BotText.key == key)
                if lang:
                    stmt = stmt.where(BotText.lang == lang)
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
                            lang=lang,
                            banner_url=banner_url,
                            banner_position=banner_position,
                        )
                    )
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def set_banner(
        self, key: str, banner_url: str | None, banner_position: str | None, lang: str | None = None
    ) -> bool:
        """Set banner URL and position for a bot text"""
        try:
            async with Session() as session:
                stmt = select(BotText).where(BotText.key == key)
                if lang:
                    stmt = stmt.where(BotText.lang == lang)
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
                stmt = select(BotText).where(BotText.key == key)
                if lang:
                    stmt = stmt.where(BotText.lang == lang)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    await session.delete(existing)
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError:
            return False

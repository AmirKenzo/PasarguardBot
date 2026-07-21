from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.settings import (
    SETTINGS_CONFIG_KEYS,
    Settings,
    default_settings_sections,
    resolve_settings_update_kwargs,
)
from app.logger import get_logger

log = get_logger(__name__)


def _apply_settings_updates(setting: Settings, kwargs: dict) -> None:
    updates = resolve_settings_update_kwargs(setting, **kwargs)
    for column, value in updates.items():
        setattr(setting, column, value)


class SettingsManager:
    async def get_settings(self):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings))
                return result.scalars().one_or_none()
        except SQLAlchemyError as e:
            log.error("Error retrieving settings", exc_info=e)
            return None

    async def add_default_settings(self):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings))
                if result.scalars().one_or_none() is None:
                    session.add(Settings(**default_settings_sections()))
                    await session.commit()
        except SQLAlchemyError as e:
            log.error("Error adding default settings", exc_info=e)

    async def add_setting(self, **kwargs):
        try:
            async with Session() as session:
                sections = default_settings_sections()
                updates = resolve_settings_update_kwargs(None, **kwargs)
                sections.update(updates)
                new_setting = Settings(**sections)
                session.add(new_setting)
                await session.commit()
                return new_setting
        except SQLAlchemyError as e:
            log.error("Error adding setting", exc_info=e)
            return None

    async def get_setting_by_id(self, setting_id):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings).filter_by(id=setting_id))
                return result.scalars().first()
        except SQLAlchemyError as e:
            log.error("Error retrieving setting", exc_info=e)
            return None

    async def get_all_settings(self):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings))
                return result.scalars().all()
        except SQLAlchemyError as e:
            log.error("Error retrieving settings", exc_info=e)
            return None

    async def update_setting(self, setting_id, **kwargs):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings).filter_by(id=setting_id))
                setting = result.scalars().first()
                if setting:
                    _apply_settings_updates(setting, kwargs)
                    await session.commit()
                    return setting
            return None
        except SQLAlchemyError as e:
            log.error("Error updating setting", exc_info=e)
            return None

    async def delete_setting(self, setting_id):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings).filter_by(id=setting_id))
                setting = result.scalars().first()
                if setting:
                    await session.delete(setting)
                    await session.commit()
                    return True
            return False
        except SQLAlchemyError as e:
            log.error("Error deleting setting", exc_info=e)
            return False

    async def toggle_mode(self, setting_id, mode_name):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings).filter_by(id=setting_id))
                setting = result.scalars().first()
                if setting and mode_name in SETTINGS_CONFIG_KEYS:
                    current_value = bool(getattr(setting, mode_name))
                    _apply_settings_updates(setting, {mode_name: not current_value})
                    await session.commit()
                    return setting
            return None
        except SQLAlchemyError as e:
            log.error("Error toggling mode", exc_info=e)
            return None

    async def update_setting_by_name(self, setting_name, value):
        try:
            async with Session() as session:
                result = await session.execute(select(Settings))
                setting = result.scalars().first()
                if setting and setting_name in SETTINGS_CONFIG_KEYS:
                    _apply_settings_updates(setting, {setting_name: value})
                    await session.commit()
                    return setting
            return None
        except SQLAlchemyError as e:
            log.error("Error updating setting by name", exc_info=e)
            return None

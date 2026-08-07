from datetime import datetime

from sqlalchemy import and_, delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import get_db
from app.db.models.app_files import AppFile


class AppFileManager:
    def __init__(self):
        pass

    async def create_app_file(
        self,
        app_key: str,
        file_name: str,
        file_url: str,
        message_id: int,
        chat_id: int,
        topic_id: int | None = None,
        tag_name: str | None = None,
        file_size_mb: float | None = None,
    ) -> AppFile:
        """Create a new app file record"""
        async for db in get_db():
            try:
                app_file = AppFile(
                    app_key=app_key,
                    file_name=file_name,
                    file_url=file_url,
                    message_id=message_id,
                    chat_id=chat_id,
                    topic_id=topic_id,
                    tag_name=tag_name,
                    file_size_mb=file_size_mb,
                )
                db.add(app_file)
                await db.commit()
                return app_file
            except SQLAlchemyError as e:
                await db.rollback()
                raise e
        return None

    async def get_app_file_by_key_and_name(self, app_key: str, file_name: str) -> AppFile | None:
        """Get app file by app_key and file_name"""
        async for db in get_db():
            stmt = select(AppFile).where(and_(AppFile.app_key == app_key, AppFile.file_name == file_name))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        return None

    async def get_app_files_by_key(self, app_key: str) -> list[AppFile]:
        """Get all app files for a specific app_key"""
        async for db in get_db():
            stmt = select(AppFile).where(AppFile.app_key == app_key).order_by(AppFile.created_at.desc())
            result = await db.execute(stmt)
            files = list(result.scalars().all())
            for f in files:
                db.expunge(f)
            return files
        return None

    async def get_default_app_file(self, app_key: str) -> AppFile | None:
        """Get the default app file for an app (most recent one)"""
        async for db in get_db():
            stmt = select(AppFile).where(AppFile.app_key == app_key).order_by(AppFile.created_at.desc()).limit(1)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        return None

    async def update_app_file(
        self,
        app_file_id: int,
        message_id: int | None = None,
        chat_id: int | None = None,
        topic_id: int | None = None,
        tag_name: str | None = None,
        file_size_mb: float | None = None,
    ) -> AppFile | None:
        """Update an existing app file"""
        async for db in get_db():
            try:
                app_file = await db.get(AppFile, app_file_id)
                if not app_file:
                    return None

                if message_id is not None:
                    app_file.message_id = message_id
                if chat_id is not None:
                    app_file.chat_id = chat_id
                if topic_id is not None:
                    app_file.topic_id = topic_id
                if tag_name is not None:
                    app_file.tag_name = tag_name
                if file_size_mb is not None:
                    app_file.file_size_mb = file_size_mb

                app_file.updated_at = datetime.utcnow()
                await db.commit()
                return app_file
            except SQLAlchemyError as e:
                await db.rollback()
                raise e
        return None

    async def delete_app_file(self, app_file_id: int) -> bool:
        """Delete an app file record"""
        async for db in get_db():
            try:
                app_file = await db.get(AppFile, app_file_id)
                if not app_file:
                    return False

                await db.delete(app_file)
                await db.commit()
                return True
            except SQLAlchemyError as e:
                await db.rollback()
                raise e
        return None

    async def delete_app_files_by_key(self, app_key: str) -> int:
        """Delete all app files for a specific app_key"""
        async for db in get_db():
            try:
                stmt = delete(AppFile).where(AppFile.app_key == app_key)
                result = await db.execute(stmt)
                await db.commit()
                return result.rowcount
            except SQLAlchemyError as e:
                await db.rollback()
                raise e
        return None

    async def delete_app_files_by_key_except_tag(self, app_key: str, keep_tag_name: str) -> int:
        """Delete stored files for an app that belong to older releases."""
        async for db in get_db():
            try:
                stmt = delete(AppFile).where(
                    and_(
                        AppFile.app_key == app_key,
                        AppFile.tag_name != keep_tag_name,
                    )
                )
                result = await db.execute(stmt)
                await db.commit()
                return result.rowcount
            except SQLAlchemyError as e:
                await db.rollback()
                raise e
        return None

    async def get_all_app_files(self) -> list[AppFile]:
        """Get all app files"""
        async for db in get_db():
            stmt = select(AppFile).order_by(AppFile.app_key, AppFile.created_at.desc())
            result = await db.execute(stmt)
            return list(result.scalars().all())
        return None

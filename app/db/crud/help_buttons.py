from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.sql import func

from app.db.base import AsyncSessionLocal as Session
from app.db.models.help_buttons import HelpButton


class HelpButtonCRUD:
    async def get_button(self, button_number: int) -> HelpButton | None:

        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.button_number == button_number)
                result = await session.execute(stmt)
                return result.scalars().first()
        except SQLAlchemyError:
            return None

    async def get_by_id(self, button_id: int) -> HelpButton | None:

        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.id == button_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except SQLAlchemyError:
            return None

    async def swap_button_numbers(self, id_a: int, id_b: int) -> bool:

        try:
            async with Session() as session:
                stmt_a = select(HelpButton).where(HelpButton.id == id_a)
                stmt_b = select(HelpButton).where(HelpButton.id == id_b)
                r_a = await session.execute(stmt_a)
                r_b = await session.execute(stmt_b)
                btn_a = r_a.scalars().first()
                btn_b = r_b.scalars().first()
                if not btn_a or not btn_b:
                    return False
                num_a, num_b = btn_a.button_number, btn_b.button_number
                if num_a == num_b:
                    return True
                max_num = await session.execute(select(func.max(HelpButton.button_number)))
                temp = (max_num.scalar() or 0) + 1
                btn_a.button_number = temp
                await session.flush()
                btn_b.button_number = num_a
                btn_a.button_number = num_b
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def reorder_by_ids(self, ordered_ids: list[int]) -> bool:
        """Assign button_number 1 to first id, 2 to second, etc. Uses temp values to avoid unique violation."""
        if not ordered_ids:
            return True
        try:
            async with Session() as session:
                offset = 10000
                for i, bid in enumerate(ordered_ids):
                    stmt = select(HelpButton).where(HelpButton.id == bid)
                    r = await session.execute(stmt)
                    btn = r.scalars().first()
                    if btn:
                        btn.button_number = offset + i
                await session.flush()
                for i, bid in enumerate(ordered_ids):
                    stmt = select(HelpButton).where(HelpButton.id == bid)
                    r = await session.execute(stmt)
                    btn = r.scalars().first()
                    if btn:
                        btn.button_number = i + 1
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def set_button_number(self, button_id: int, new_number: int) -> bool:
        """Set one button's button_number to new_number. If new_number is taken, swap with that button."""
        if new_number < 1:
            return False
        try:
            async with Session() as session:
                stmt_btn = select(HelpButton).where(HelpButton.id == button_id)
                r_btn = await session.execute(stmt_btn)
                btn = r_btn.scalars().first()
                if not btn:
                    return False
                old_num = btn.button_number
                if old_num == new_number:
                    await session.commit()
                    return True
                stmt_other = select(HelpButton).where(HelpButton.button_number == new_number)
                r_other = await session.execute(stmt_other)
                other = r_other.scalars().first()
                if other:
                    max_num = await session.execute(select(func.max(HelpButton.button_number)))
                    temp = (max_num.scalar() or 0) + 1
                    btn.button_number = temp
                    await session.flush()
                    other.button_number = old_num
                    btn.button_number = new_number
                else:
                    btn.button_number = new_number
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def set_button(
        self,
        button_number: int,
        button_text: str | None = None,
        button_url: str | None = None,
        button_style: str | None = None,
        button_icon: int | None = None,
        *,
        clear_icon: bool = False,
    ) -> bool:

        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.button_number == button_number)
                result = await session.execute(stmt)
                existing = result.scalars().first()
                if existing:
                    if button_text is not None:
                        existing.button_text = button_text
                    if button_url is not None:
                        existing.button_url = button_url
                    if button_style is not None:
                        existing.button_style = button_style if button_style else None
                    if clear_icon or button_icon is not None:
                        existing.button_icon = None if clear_icon else button_icon
                else:
                    session.add(
                        HelpButton(
                            button_number=button_number,
                            button_text=button_text,
                            button_url=button_url,
                            button_style=button_style,
                            button_icon=button_icon,
                        )
                    )
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def get_all_buttons(self) -> list[HelpButton]:

        try:
            async with Session() as session:
                stmt = select(HelpButton).order_by(HelpButton.button_number)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except SQLAlchemyError:
            return []

    async def delete_button(self, button_number: int) -> bool:

        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.button_number == button_number)
                result = await session.execute(stmt)
                button = result.scalars().first()
                if button:
                    await session.delete(button)
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError:
            return False

    async def initialize_default_buttons(self):
        try:
            async with Session() as session:
                result = await session.execute(
                    select(HelpButton.button_number).where(HelpButton.button_number.in_(list(range(1, 9))))
                )
                existing = set(result.scalars().all())
                missing = [
                    HelpButton(button_number=i, button_text=None, button_url=None)
                    for i in range(1, 9)
                    if i not in existing
                ]
                if missing:
                    session.add_all(missing)
                    await session.commit()
        except SQLAlchemyError:
            pass


class HelpDownloadAppCRUD:
    async def get_all(self, order_by_number: bool = True) -> list[HelpButton]:
        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.callback_key.isnot(None))
                if order_by_number:
                    stmt = stmt.order_by(HelpButton.button_number.asc(), HelpButton.id.asc())
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except SQLAlchemyError:
            return []

    async def get_by_id(self, app_id: int) -> HelpButton | None:
        try:
            async with Session() as session:
                stmt = select(HelpButton).where(
                    HelpButton.id == app_id,
                    HelpButton.callback_key.isnot(None),
                )
                result = await session.execute(stmt)
                return result.scalars().first()
        except SQLAlchemyError:
            return None

    async def get_by_callback_key(self, callback_key: str) -> HelpButton | None:
        try:
            async with Session() as session:
                stmt = select(HelpButton).where(HelpButton.callback_key == callback_key)
                result = await session.execute(stmt)
                return result.scalars().first()
        except SQLAlchemyError:
            return None

    async def create(
        self,
        button_text: str,
        callback_key: str,
        repo_owner: str,
        repo_name: str,
        categories: dict,
        default_file: str | None = None,
        ios_url: str | None = None,
        download_targets: list | None = None,
    ) -> HelpButton | None:
        callback_key = callback_key.strip().lower().replace(" ", "_")
        try:
            async with Session() as session:
                max_num = await session.execute(select(func.max(HelpButton.button_number)))
                next_num = (max_num.scalar() or 0) + 1
                max_id = await session.execute(select(func.max(HelpButton.id)))
                next_id = (max_id.scalar() or 0) + 1

                btn = HelpButton(
                    id=next_id,
                    button_number=next_num,
                    button_text=button_text.strip(),
                    button_url=None,
                    callback_key=callback_key,
                    repo_owner=repo_owner.strip(),
                    repo_name=repo_name.strip(),
                    categories=categories,
                    download_targets=download_targets,
                    default_file=default_file.strip() if default_file else None,
                    ios_url=ios_url.strip() if ios_url else None,
                )
                session.add(btn)
                await session.commit()
                return btn
        except SQLAlchemyError:
            return None

    async def create_text_only(
        self,
        button_text: str,
        callback_key: str,
        custom_message: str,
    ) -> HelpButton | None:
        """Create a text-only entry (no GitHub). When user clicks, show custom_message."""
        callback_key = callback_key.strip().lower().replace(" ", "_")
        try:
            async with Session() as session:
                max_num = await session.execute(select(func.max(HelpButton.button_number)))
                next_num = (max_num.scalar() or 0) + 1
                max_id = await session.execute(select(func.max(HelpButton.id)))
                next_id = (max_id.scalar() or 0) + 1
                btn = HelpButton(
                    id=next_id,
                    button_number=next_num,
                    button_text=button_text.strip(),
                    button_url=None,
                    callback_key=callback_key,
                    repo_owner=None,
                    repo_name=None,
                    categories=None,
                    default_file=None,
                    ios_url=None,
                    custom_message=(custom_message or "").strip() or None,
                )
                session.add(btn)
                await session.commit()
                return btn
        except SQLAlchemyError:
            return None

    async def update(
        self,
        app_id: int,
        *,
        button_text: str | None = None,
        callback_key: str | None = None,
        repo_owner: str | None = None,
        repo_name: str | None = None,
        categories: dict | None = None,
        download_targets: list | None = None,
        default_file: str | None = None,
        ios_url: str | None = None,
        custom_message: str | None = None,
        button_style: str | None = None,
        button_icon: int | None = None,
        clear_icon: bool = False,
    ) -> bool:
        try:
            async with Session() as session:
                stmt = select(HelpButton).where(
                    HelpButton.id == app_id,
                    HelpButton.callback_key.isnot(None),
                )
                result = await session.execute(stmt)
                app = result.scalars().first()
                if not app:
                    return False
                if button_text is not None:
                    app.button_text = button_text.strip()
                if callback_key is not None:
                    app.callback_key = callback_key.strip().lower().replace(" ", "_")
                if repo_owner is not None:
                    app.repo_owner = repo_owner.strip()
                if repo_name is not None:
                    app.repo_name = repo_name.strip()
                if categories is not None:
                    app.categories = categories
                if download_targets is not None:
                    app.download_targets = download_targets
                if default_file is not None:
                    app.default_file = default_file.strip() or None
                if ios_url is not None:
                    app.ios_url = ios_url.strip() or None
                if custom_message is not None:
                    app.custom_message = custom_message.strip() or None
                if button_style is not None:
                    app.button_style = button_style.strip() or None
                if clear_icon or button_icon is not None:
                    app.button_icon = None if clear_icon else button_icon
                await session.commit()
                return True
        except SQLAlchemyError:
            return False

    async def delete(self, app_id: int) -> bool:
        try:
            async with Session() as session:
                stmt = select(HelpButton).where(
                    HelpButton.id == app_id,
                    HelpButton.callback_key.isnot(None),
                )
                result = await session.execute(stmt)
                app = result.scalars().first()
                if app:
                    await session.delete(app)
                    await session.commit()
                    return True
                return False
        except SQLAlchemyError:
            return False

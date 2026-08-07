from sqlalchemy import func
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.panels import Panels
from app.db.models.services import Service
from app.logger import get_logger
from app.services.panels.settings import (
    default_panel_json_settings,
    panel_shop_sale_enabled,
    panel_user_limit,
    parse_group_ids_value,
    resolve_panel_update_kwargs,
)
from app.utils.formatting.conversions import as_int

log = get_logger(__name__)


class PanelsManager:
    def __init__(self):
        pass

    async def add_panel(
        self,
        code,
        name,
        enable,
        base_url,
        username,
        password,
        cookie,
        tunnel_url=None,
        default_group_ids=None,
        user_limit=None,
        auth_type="password",
    ):
        group_ids = parse_group_ids_value(default_group_ids)
        json_settings = default_panel_json_settings(
            default_group_ids=group_ids or None,
            user_limit=user_limit,
        )
        async with Session() as session:
            new_panel = Panels(
                code=code,
                name=name,
                enable=enable,
                base_url=base_url,
                username=username,
                password=password,
                cookie=cookie,
                tunnel_url=tunnel_url,
                auth_type=auth_type,
                **json_settings,
            )
            session.add(new_panel)
            await session.commit()
            return new_panel

    async def get_all_panels(self):
        async with Session() as session:
            result = await session.execute(select(Panels))
            return result.scalars().all()

    async def get_all_panels_reverse(self):
        async with Session() as session:
            result = await session.execute(select(Panels).order_by(Panels.code.desc()))
            return result.scalars().all()

    async def get_panel_by_code(self, code):
        panel_code = as_int(code)
        if panel_code is None:
            return None
        async with Session() as session:
            result = await session.execute(select(Panels).filter_by(code=panel_code))
            return result.scalars().first()

    async def update_panel(self, code, **kwargs):
        panel_code = as_int(code)
        if panel_code is None:
            log.debug("Panel not found")
            return False
        async with Session() as session:
            result = await session.execute(select(Panels).filter_by(code=panel_code))
            panel = result.scalars().first()
            if panel:
                try:
                    resolved = resolve_panel_update_kwargs(panel, **kwargs)
                    for key, value in resolved.items():
                        setattr(panel, key, value)
                    await session.commit()
                    return True
                except Exception as e:
                    await session.rollback()
                    log.error("Panel update failed: %s", e)
                    return False
            else:
                log.debug("Panel not found")
                return False

    async def delete_panel(self, code):
        async with Session() as session:
            panel = await self.get_panel_by_code(code)
            if panel:
                await session.delete(panel)
                await session.commit()
                return True
            return False

    async def count_panels(self) -> int:
        async with Session() as session:
            result = await session.execute(select(func.count()).select_from(Panels))
            return int(result.scalar() or 0)

    async def search_by_field(self, field_name, value):
        async with Session() as session:
            result = await session.execute(select(Panels).filter(getattr(Panels, field_name) == value))
            return result.scalars().all()

    async def count_panel_users(self, panel_code):
        """English docstring for count_panel_users."""
        code = as_int(panel_code)
        if code is None:
            return 0
        async with Session() as session:
            result = await session.execute(select(func.count()).select_from(Service).filter(Service.in_panel == code))
            return result.scalar() or 0

    async def get_panel_user_counts(self) -> dict[int, int]:
        """One GROUP BY query: panel code -> service count."""
        async with Session() as session:
            result = await session.execute(
                select(Service.in_panel, func.count()).select_from(Service).group_by(Service.in_panel)
            )
            return {int(panel_code): int(count or 0) for panel_code, count in result.all() if panel_code is not None}

    async def is_panel_at_capacity(self, panel_code):
        """English docstring for is_panel_at_capacity."""
        panel = await self.get_panel_by_code(panel_code)
        limit = panel_user_limit(panel) if panel else None
        if not panel or limit is None:
            return False

        code = as_int(panel_code)
        if code is None:
            return False
        counts = await self.get_panel_user_counts()
        return counts.get(code, 0) >= limit

    async def get_available_panels(self):
        """English docstring for get_available_panels."""
        all_panels = await self.get_all_panels()
        counts = await self.get_panel_user_counts()
        available_panels = []

        for panel in all_panels:
            if not panel_shop_sale_enabled(panel):
                continue

            limit = panel_user_limit(panel)
            if limit is None:
                available_panels.append(panel)
                continue

            if counts.get(panel.code, 0) < limit:
                available_panels.append(panel)

        return available_panels

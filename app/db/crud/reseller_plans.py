import json

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.models.reseller_plans import ResellerPlan
from app.logger import get_logger
from app.utils.formatting.conversions import as_int

log = get_logger(__name__)


class ResellerPlanManager:
    async def add_plan(self, **kwargs) -> ResellerPlan | None:
        try:
            async with Session() as session:
                plan = ResellerPlan(**kwargs)
                session.add(plan)
                await session.commit()
                return plan
        except SQLAlchemyError as e:
            log.error("Failed to add reseller plan: %s", e)
            return None

    async def get_plan(self, plan_id) -> ResellerPlan | None:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return None
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerPlan).filter_by(id=plan_id))
                return result.scalars().first()
        except SQLAlchemyError as e:
            log.error("Failed to get reseller plan: %s", e)
            return None

    async def get_all_plans(self, panel_code=None, enabled_only=False) -> list[ResellerPlan]:
        try:
            async with Session() as session:
                stmt = select(ResellerPlan)
                if panel_code is not None:
                    coerced = as_int(panel_code)
                    if coerced is None:
                        return []
                    stmt = stmt.where(ResellerPlan.panel_code == coerced)
                if enabled_only:
                    stmt = stmt.where(ResellerPlan.enable.is_(True))
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list reseller plans: %s", e)
            return []

    async def get_panels_with_plans(self, enabled_only=True) -> list[int]:
        plans = await self.get_all_plans(enabled_only=enabled_only)
        return sorted({p.panel_code for p in plans})

    async def update_plan(self, plan_id, **kwargs) -> bool:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerPlan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if not plan:
                    return False
                for key, value in kwargs.items():
                    if hasattr(plan, key):
                        setattr(plan, key, value)
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to update reseller plan: %s", e)
            return False

    async def delete_plan(self, plan_id) -> tuple[bool, str]:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return False, "پلن یافت نشد."
        linked = await ResellerAccountCRUD().count_accounts_by_plan(plan_id)
        if linked > 0:
            return False, f"این پلن روی {linked} نمایندگی استفاده شده و قابل حذف نیست."
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerPlan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if not plan:
                    return False, "پلن یافت نشد."
                await session.delete(plan)
                await session.commit()
                return True, "پلن حذف شد."
        except SQLAlchemyError as e:
            log.error("Failed to delete reseller plan: %s", e)
            return False, "خطا در حذف پلن."

    @staticmethod
    def parse_json_field(raw: str | None) -> dict | list | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except TypeError, json.JSONDecodeError:
            return None

    @staticmethod
    def dump_json_field(value) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

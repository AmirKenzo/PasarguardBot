from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.plans import Plan
from app.logger import get_logger
from app.utils.formatting.conversions import as_int

log = get_logger(__name__)


class PlanManager:
    async def add_plan(
        self, price, storage, duration, panel_code, plan_type="volume", data_limit_reset_strategy="no_reset", ip_limit=0
    ):

        try:
            async with Session() as session:
                new_plan = Plan(
                    price=price,
                    storage=storage,
                    duration=duration,
                    panel_code=panel_code,
                    plan_type=plan_type,
                    data_limit_reset_strategy=data_limit_reset_strategy,
                    ip_limit=ip_limit,
                )
                session.add(new_plan)
                await session.commit()

                plan_type_text = "حجمی" if plan_type == "volume" else "مصرف منصفانه"
                reset_text = {
                    "no_reset": "بدون ریست",
                    "day": "روزانه",
                    "week": "هفتگی",
                    "month": "ماهانه",
                    "year": "سالانه",
                }.get(data_limit_reset_strategy, "بدون ریست")
                ip_limit_text = "نامحدود" if ip_limit == 0 else f"{ip_limit} کاربر"

                return f"پلن {plan_type_text} با قیمت {price}، حجم {storage} گیگابایت، زمان {duration} روز، ریست {reset_text} و محدودیت کاربر {ip_limit_text} اضافه شد."
        except SQLAlchemyError as e:
            return f"خطا در افزودن پنل: {e}"

    async def get_all_plans(self, panel_code=None, duration=None):

        try:
            async with Session() as session:
                stmt = select(Plan)
                if panel_code:
                    coerced_panel_code = as_int(panel_code)
                    if coerced_panel_code is None:
                        return []
                    stmt = stmt.where(Plan.panel_code == coerced_panel_code)
                if duration is not None:
                    coerced_duration = as_int(duration)
                    if coerced_duration is None:
                        return []
                    stmt = stmt.where(Plan.duration == coerced_duration)
                result = await session.execute(stmt)
                return result.scalars().all()
        except SQLAlchemyError as e:
            log.error("Failed to fetch plans: %s", e)
            return []

    async def get_unique_durations(self, panel_code):

        coerced_panel_code = as_int(panel_code)
        if coerced_panel_code is None:
            return []
        try:
            async with Session() as session:
                stmt = select(Plan.duration).where(Plan.panel_code == coerced_panel_code).distinct()
                result = await session.execute(stmt)
                return sorted([row[0] for row in result.all()])
        except SQLAlchemyError as e:
            log.error("Failed to fetch durations: %s", e)
            return []

    async def get_unique_durations_for_panels(self, panel_codes: list) -> dict[int, list[int]]:
        """Distinct durations per panel, batched in one query. Missing/invalid codes map to []."""
        coerced_codes = [code for code in (as_int(c) for c in panel_codes) if code is not None]
        result_by_panel: dict[int, list[int]] = {code: [] for code in coerced_codes}
        if not coerced_codes:
            return result_by_panel

        try:
            async with Session() as session:
                stmt = select(Plan.panel_code, Plan.duration).where(Plan.panel_code.in_(coerced_codes)).distinct()
                result = await session.execute(stmt)
                for panel_code, duration in result.all():
                    result_by_panel.setdefault(int(panel_code), []).append(duration)
        except SQLAlchemyError as e:
            log.error("Failed to fetch durations for panels: %s", e)
            return result_by_panel

        for code in result_by_panel:
            result_by_panel[code] = sorted(result_by_panel[code])
        return result_by_panel

    async def update_plan(self, plan_id, new_price=None, new_storage=None, new_duration=None, new_ip_limit=None):

        plan_id = as_int(plan_id)
        if plan_id is None:
            return
        try:
            async with Session() as session:
                result = await session.execute(select(Plan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if plan:
                    if new_price is not None:
                        plan.price = new_price
                    if new_storage is not None:
                        plan.storage = new_storage
                    if new_duration is not None:
                        plan.duration = new_duration
                    if new_ip_limit is not None:
                        plan.ip_limit = new_ip_limit
                    await session.commit()
                    log.debug("Plan updated plan_id=%s", plan_id)
                else:
                    log.debug("Plan not found plan_id=%s", plan_id)
        except SQLAlchemyError as e:
            log.error("Plan update failed: %s", e)

    async def update_plan_display(
        self,
        plan_id: int,
        *,
        display_button_text: str | None = None,
        button_style: str | None = None,
        button_icon: int | None = None,
        set_display_button_text: bool = False,
        set_button_style: bool = False,
        set_button_icon: bool = False,
        clear_button_icon: bool = False,
    ) -> bool:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(Plan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if not plan:
                    return False
                if set_display_button_text:
                    plan.display_button_text = display_button_text
                if set_button_style:
                    plan.button_style = button_style
                if set_button_icon:
                    plan.button_icon = button_icon
                if clear_button_icon:
                    plan.button_icon = None
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Plan display update failed: %s", e)
            return False

    async def reset_plan_display_button(self, plan_id: int) -> bool:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(Plan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if not plan:
                    return False
                plan.display_button_text = None
                plan.button_style = None
                plan.button_icon = None
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Plan display reset failed: %s", e)
            return False

    async def bulk_update_plans(self, updates: list):
        """
        Bulk update plans
        updates: List of dictionaries containing plan_id and updateable fields
        Example: [{"plan_id": 1, "price": 50000, "storage": 10.5, "duration": 30, "ip_limit": 1}, ...]
        Updates only price, storage, duration, ip_limit fields
        """
        updated_count = 0
        errors = []
        changed_plans = []

        try:
            async with Session() as session:
                for update_data in updates:
                    plan_id = update_data.get("plan_id")
                    if not plan_id:
                        errors.append("ID پلن مشخص نشده است")
                        continue

                    result = await session.execute(select(Plan).filter_by(id=plan_id))
                    plan = result.scalars().first()

                    if not plan:
                        errors.append(f"پلن با ID {plan_id} یافت نشد")
                        continue

                    has_changes = False
                    old_values = {
                        "price": plan.price,
                        "storage": plan.storage,
                        "duration": plan.duration,
                        "ip_limit": plan.ip_limit,
                    }
                    new_values = {}

                    if "price" in update_data:
                        new_price = float(update_data["price"])
                        if plan.price != new_price:
                            has_changes = True
                            plan.price = new_price
                            new_values["price"] = new_price
                    if "storage" in update_data:
                        new_storage = float(update_data["storage"])
                        if plan.storage != new_storage:
                            has_changes = True
                            plan.storage = new_storage
                            new_values["storage"] = new_storage
                    if "duration" in update_data:
                        new_duration = int(update_data["duration"])
                        if plan.duration != new_duration:
                            has_changes = True
                            plan.duration = new_duration
                            new_values["duration"] = new_duration
                    if "ip_limit" in update_data:
                        new_ip_limit = int(update_data["ip_limit"])
                        if plan.ip_limit != new_ip_limit:
                            has_changes = True
                            plan.ip_limit = new_ip_limit
                            new_values["ip_limit"] = new_ip_limit

                    if has_changes:
                        updated_count += 1
                        changed_plans.append(
                            {
                                "plan_id": plan_id,
                                "old_values": old_values,
                                "new_values": new_values,
                            }
                        )

                await session.commit()
                return {
                    "success": True,
                    "updated_count": updated_count,
                    "errors": errors,
                    "changed_plans": changed_plans,
                }
        except SQLAlchemyError as e:
            await session.rollback()
            return {"success": False, "updated_count": updated_count, "errors": [f"خطا در به‌روزرسانی: {e}"]}

    async def delete_plan(self, plan_id):
        plan_id = as_int(plan_id)
        if plan_id is None:
            return
        try:
            async with Session() as session:
                result = await session.execute(select(Plan).filter_by(id=plan_id))
                plan = result.scalars().first()
                if plan:
                    await session.delete(plan)
                    await session.commit()
                    log.debug("Plan deleted plan_id=%s", plan_id)
                else:
                    log.debug("Plan not found plan_id=%s", plan_id)
        except SQLAlchemyError as e:
            log.error("Plan delete failed: %s", e)

    async def get_plan(self, plan_id):
        plan_id = as_int(plan_id)
        if plan_id is None:
            return None
        try:
            async with Session() as session:
                result = await session.execute(select(Plan).filter_by(id=plan_id))
                return result.scalars().first()
        except SQLAlchemyError as e:
            log.error("Failed to get plan: %s", e)
            return None

    async def get_plan_by_volume_for_display(self, gb, panel_code):

        panel_code = as_int(panel_code)
        if panel_code is None:
            return None
        try:
            gb = float(gb)
            tolerance = 0.001
            async with Session() as session:
                result = await session.execute(
                    select(Plan).filter(
                        and_(
                            Plan.storage >= gb - tolerance,
                            Plan.storage <= gb + tolerance,
                            Plan.panel_code == panel_code,
                            Plan.plan_type.in_(["fair_usage", "fair"]),
                        )
                    )
                )
                plan = result.scalars().first()

                if plan:
                    return plan

                result = await session.execute(
                    select(Plan).filter(
                        and_(
                            Plan.storage >= gb - tolerance,
                            Plan.storage <= gb + tolerance,
                            Plan.panel_code == panel_code,
                            Plan.plan_type == "volume",
                        )
                    )
                )
                plan = result.scalars().first()

                if plan:
                    return plan

                result = await session.execute(
                    select(Plan).filter(
                        and_(
                            Plan.storage >= gb - tolerance,
                            Plan.storage <= gb + tolerance,
                            Plan.panel_code == panel_code,
                        )
                    )
                )
                return result.scalars().first()

        except Exception as e:
            log.error("Plan operation failed: %s", e)
            return None

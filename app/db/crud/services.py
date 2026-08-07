import time

from sqlalchemy import String, and_, case, cast, delete, distinct, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.panels import Panels
from app.db.models.services import Service
from app.logger import get_logger
from app.utils.formatting.conversions import as_int

logger = get_logger(__name__)


class ServiceCRUD:
    async def create_service(self, **kwargs):
        try:
            async with Session() as session:
                new_service = Service(**kwargs)
                session.add(new_service)
                await session.commit()
                return True, "Service created successfully."
        except SQLAlchemyError as e:
            return False, f"Error in creating service: {e}"

    async def get_service(self, code):
        try:
            service_code = as_int(code)
            if service_code is None:
                return False, "Service not found."
            async with Session() as session:
                service = await session.execute(select(Service).filter_by(code=service_code))
                service = service.scalars().first()
                if service:
                    return True, service
                return False, "Service not found."
        except SQLAlchemyError as e:
            return False, f"Error in getting service: {e}"

    async def get_services_reverse(self, user_id):
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service).filter_by(id=user_id).order_by(Service.createtime.desc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error: {e}")
            return []

    async def get_services_by_user_and_usernames(self, user_id: int, usernames: list[str]) -> list:
        """Get services for a user whose username (case-sensitive) is in the given list."""
        if not usernames:
            return []
        requested = [n.strip() for n in usernames if n and n.strip()]
        if not requested:
            return []
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service)
                    .where(Service.id == user_id, Service.username.in_(requested))
                    .order_by(Service.createtime.desc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error get_services_by_user_and_usernames: {e}")
            return []

    async def get_services_by_panel_and_usernames(self, panel_code: int, usernames: list[str]) -> list:
        """Get services for one panel whose username is in the given list."""
        if not usernames:
            return []
        requested = [n.strip() for n in usernames if n and n.strip()]
        if not requested:
            return []
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service).where(
                        Service.in_panel == panel_code,
                        Service.username.in_(requested),
                    )
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error get_services_by_panel_and_usernames: {e}")
            return []

    async def get_services_by_usernames(self, usernames: list[str]) -> list:
        """Get all services whose username (case-sensitive) is in the given list. No owner filter."""
        if not usernames:
            return []
        requested = [n.strip() for n in usernames if n and n.strip()]
        if not requested:
            return []
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service).where(Service.username.in_(requested)).order_by(Service.createtime.desc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error get_services_by_usernames: {e}")
            return []

    async def update_service(self, code, **kwargs):
        try:
            service_code = as_int(code)
            if service_code is None:
                return False, "Service not found."
            async with Session() as session:
                result = await session.execute(select(Service).filter_by(code=service_code))
                service = result.scalars().first()
                if not service:
                    return False, "Service not found."

                for key, value in kwargs.items():
                    if hasattr(service, key):
                        setattr(service, key, value)

                await session.commit()
                return True, "Service updated successfully."
        except SQLAlchemyError as e:
            return False, f"Error in updating service: {e}"

    async def bulk_update_services(self, updates: list[tuple[int, dict]]) -> tuple[int, int]:
        """Update multiple services in one transaction. Each item is (service_code, fields)."""
        if not updates:
            return 0, 0

        service_codes = []
        fields_by_code = {}
        for code, fields in updates:
            service_code = as_int(code)
            if service_code is None or not fields:
                continue
            service_codes.append(service_code)
            fields_by_code[service_code] = fields

        if not service_codes:
            return 0, 0

        try:
            async with Session() as session:
                result = await session.execute(select(Service).where(Service.code.in_(service_codes)))
                services = result.scalars().all()
                updated = 0

                for service in services:
                    changed = False
                    for key, value in fields_by_code.get(service.code, {}).items():
                        if hasattr(service, key):
                            setattr(service, key, value)
                            changed = True
                    if changed:
                        updated += 1

                if updated:
                    await session.commit()
                return len(services), updated
        except SQLAlchemyError as e:
            logger.error(f"DB Error bulk updating services: {e}")
            return 0, 0

    async def update_panel_userids_by_username(
        self, panel_code: int, panel_userids_by_username: dict[str, int]
    ) -> tuple[int, int]:
        """Update panel numeric user IDs for one panel batch, matched by username."""
        usernames = [username for username in panel_userids_by_username if username]
        if not usernames:
            return 0, 0

        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service).where(
                        Service.in_panel == panel_code,
                        Service.username.in_(usernames),
                    )
                )
                services = result.scalars().all()
                updated = 0
                for service in services:
                    panel_userid = panel_userids_by_username.get(service.username)
                    if panel_userid is None or service.panel_userid == panel_userid:
                        continue
                    service.panel_userid = panel_userid
                    updated += 1

                if updated:
                    await session.commit()
                return len(services), updated
        except SQLAlchemyError as e:
            logger.error(f"DB Error updating panel_userids: {e}")
            return 0, 0

    async def delete_service(self, code):
        try:
            service_code = as_int(code)
            if service_code is None:
                return False, "Service not found."
            async with Session() as session:
                result = await session.execute(select(Service).filter_by(code=service_code))
                service = result.scalars().first()
                if not service:
                    return False, "Service not found."

                await session.delete(service)
                await session.commit()
                return True, "Service deleted successfully."
        except SQLAlchemyError as e:
            return False, f"Error in deleting service: {e}"

    async def bulk_delete_services(self, codes: list) -> int:
        """Delete many services by code in one transaction. Returns deleted row count."""
        service_codes = []
        seen: set[int] = set()
        for code in codes:
            service_code = as_int(code)
            if service_code is None or service_code in seen:
                continue
            seen.add(service_code)
            service_codes.append(service_code)
        if not service_codes:
            return 0
        try:
            async with Session() as session:
                result = await session.execute(delete(Service).where(Service.code.in_(service_codes)))
                await session.commit()
                return int(result.rowcount or 0)
        except SQLAlchemyError as e:
            logger.error(f"DB Error bulk deleting services: {e}")
            return 0

    async def get_unique_user_ids(self):
        try:
            async with Session() as session:
                result = await session.execute(select(distinct(Service.id)))
                return result.scalars().all()
        except SQLAlchemyError as e:
            return f"Error in fetching unique user IDs: {e}"

    async def count_services(self):
        try:
            async with Session() as session:
                result = await session.execute(select(func.count()).select_from(Service))
                return result.scalar() or 0
        except SQLAlchemyError as e:
            logger.error("Error counting services: %s", e)
            return 0

    async def total_volume(self):
        try:
            async with Session() as session:
                result = await session.execute(select(func.sum(Service.package_size)))
                total = result.scalar()
                return total or 0
        except SQLAlchemyError as e:
            logger.error("Error getting total volume: %s", e)
            return 0

    async def get_top_customers_by_config_count(self, limit: int = 10) -> list[tuple[int | None, int]]:
        """(user_id, config_count) ordered by config count desc. user_id can be None for orphan services."""
        try:
            async with Session() as session:
                paid = or_(Service.is_test.is_(False), Service.is_test.is_(None))
                stmt = (
                    select(Service.id, func.count().label("cnt"))
                    .where(Service.id.isnot(None), paid)
                    .group_by(Service.id)
                    .order_by(func.count().desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return [(r.id, int(r.cnt or 0)) for r in result.all()]
        except SQLAlchemyError as e:
            logger.error(f"Error getting top customers by config: {e}")
            return []

    async def get_today_config_stats(self, today_ts: int, limit: int = 5) -> dict:
        """Configs sold today and top buyers today."""
        try:
            async with Session() as session:
                paid = or_(Service.is_test.is_(False), Service.is_test.is_(None))
                today_cond = paid & (Service.createtime.isnot(None)) & (Service.createtime >= today_ts)

                total_stmt = select(func.count()).select_from(Service).where(today_cond)
                total_today = (await session.execute(total_stmt)).scalar() or 0

                top_stmt = (
                    select(Service.id, func.count().label("cnt"))
                    .where(today_cond, Service.id.isnot(None))
                    .group_by(Service.id)
                    .order_by(func.count().desc())
                    .limit(limit)
                )
                top_rows = (await session.execute(top_stmt)).all()
                top_buyers = [(r.id, int(r.cnt or 0)) for r in top_rows]
                return {"total_today": int(total_today), "top_buyers": top_buyers}
        except SQLAlchemyError as e:
            logger.error("Error getting today config stats: %s", e)
            return {"total_today": 0, "top_buyers": []}

    async def get_period_stats(self, start_ts: int, end_ts: int | None = None) -> dict:
        """Service stats for admin dashboard filtered by createtime in [start_ts, end_ts)."""
        empty = {
            "total": 0,
            "active": 0,
            "disabled": 0,
            "test_total": 0,
            "paid_total": 0,
            "total_volume_bytes": 0,
            "paid_period": 0,
            "test_period": 0,
            "expiring_3d": 0,
            "expiring_7d": 0,
            "expired": 0,
            "top_panels": [],
            "top_volumes": [],
        }
        try:
            async with Session() as session:
                now = int(time.time())
                exp_3d = now + 3 * 86400
                exp_7d = now + 7 * 86400
                paid = or_(Service.is_test.is_(False), Service.is_test.is_(None))
                test_cond = Service.is_test.is_(True)

                def _period_cond(extra_cond=None):
                    if start_ts <= 0:
                        cond = extra_cond if extra_cond is not None else True
                    else:
                        cond = Service.createtime.isnot(None) & (Service.createtime >= start_ts)
                        if end_ts is not None:
                            cond = cond & (Service.createtime < end_ts)
                        if extra_cond is not None:
                            cond = cond & extra_cond
                    return cond

                def _period_count(extra_cond=None):
                    cond = _period_cond(extra_cond)
                    return func.sum(case((cond, 1), else_=0))

                base = await session.execute(
                    select(
                        func.count().label("total"),
                        func.sum(case((Service.enable.is_(True), 1), else_=0)).label("active"),
                        func.sum(case((Service.enable.is_(False), 1), else_=0)).label("disabled"),
                        func.sum(case((test_cond, 1), else_=0)).label("test_total"),
                        func.sum(case((paid, 1), else_=0)).label("paid_total"),
                        func.sum(Service.package_size).label("total_volume_bytes"),
                        _period_count(paid).label("paid_period"),
                        _period_count(test_cond).label("test_period"),
                        func.sum(
                            case(
                                (
                                    Service.expiration_time.isnot(None)
                                    & (Service.expiration_time > now)
                                    & (Service.expiration_time <= exp_3d),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("expiring_3d"),
                        func.sum(
                            case(
                                (
                                    Service.expiration_time.isnot(None)
                                    & (Service.expiration_time > now)
                                    & (Service.expiration_time <= exp_7d),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("expiring_7d"),
                        func.sum(
                            case((Service.expiration_time.isnot(None) & (Service.expiration_time <= now), 1), else_=0)
                        ).label("expired"),
                    ).select_from(Service)
                )
                row = base.one()

                panel_cond = [Service.in_panel.isnot(None), paid]
                if start_ts > 0:
                    panel_cond.extend([Service.createtime.isnot(None), Service.createtime >= start_ts])
                    if end_ts is not None:
                        panel_cond.append(Service.createtime < end_ts)

                panel_rows = (
                    await session.execute(
                        select(Panels.name, Service.in_panel, func.count().label("cnt"))
                        .join(Panels, Panels.code == Service.in_panel)
                        .where(*panel_cond)
                        .group_by(Panels.name, Service.in_panel)
                        .order_by(func.count().desc())
                        .limit(5)
                    )
                ).all()

                volume_cond = [paid, Service.package_size.isnot(None)]
                if start_ts > 0:
                    volume_cond.extend([Service.createtime.isnot(None), Service.createtime >= start_ts])
                    if end_ts is not None:
                        volume_cond.append(Service.createtime < end_ts)

                volume_rows = (
                    await session.execute(
                        select(Service.package_size, func.count().label("cnt"))
                        .where(*volume_cond)
                        .group_by(Service.package_size)
                        .order_by(func.count().desc())
                        .limit(5)
                    )
                ).all()

                def _panel_label(name: str | None, panel_id: int) -> str:
                    return name or f"پنل {panel_id}"

                def _volume_label(size_bytes: int | None) -> str:
                    if not size_bytes:
                        return "نامشخص"
                    gb = size_bytes / (1024**3)
                    if gb >= 1:
                        return f"{gb:.0f} GB" if gb == int(gb) else f"{gb:.1f} GB"
                    return f"{size_bytes / (1024**2):.0f} MB"

                return {
                    "total": int(row.total or 0),
                    "active": int(row.active or 0),
                    "disabled": int(row.disabled or 0),
                    "test_total": int(row.test_total or 0),
                    "paid_total": int(row.paid_total or 0),
                    "total_volume_bytes": int(row.total_volume_bytes or 0),
                    "paid_period": int(row.paid_period or 0),
                    "test_period": int(row.test_period or 0),
                    "expiring_3d": int(row.expiring_3d or 0),
                    "expiring_7d": int(row.expiring_7d or 0),
                    "expired": int(row.expired or 0),
                    "top_panels": [(_panel_label(r.name, int(r.in_panel)), int(r.cnt or 0)) for r in panel_rows],
                    "top_volumes": [(_volume_label(r.package_size), int(r.cnt or 0)) for r in volume_rows],
                }
        except SQLAlchemyError as e:
            logger.error("Error getting period service stats: %s", e)
            return empty

    async def get_stats(self) -> dict:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(
                        func.count().label("service_count"),
                        func.sum(Service.package_size).label("total_volume_bytes"),
                        func.sum(case((Service.is_test.is_(True), 1), else_=0)).label("test_services_count"),
                        func.sum(case((or_(Service.is_test.is_(False), Service.is_test.is_(None)), 1), else_=0)).label(
                            "paid_services_count"
                        ),
                    ).select_from(Service)
                )
                row = result.one()
                return {
                    "service_count": int(row.service_count or 0),
                    "total_volume_bytes": int(row.total_volume_bytes or 0),
                    "test_services_count": int(row.test_services_count or 0),
                    "paid_services_count": int(row.paid_services_count or 0),
                }
        except SQLAlchemyError as e:
            logger.error("Error getting service stats: %s", e)
            return {
                "service_count": 0,
                "total_volume_bytes": 0,
                "test_services_count": 0,
                "paid_services_count": 0,
            }

    async def has_active_service(self, user_id: int) -> bool:
        """Check if a user has at least one active service."""
        try:
            async with Session() as session:
                result = await session.execute(select(Service).filter_by(id=user_id, enable=True))
                return result.scalars().first() is not None
        except SQLAlchemyError as e:
            logger.error(f"DB Error: {e}")
            return False

    async def get_panel_active_services(self, panel_code: int):

        try:
            async with Session() as session:
                result = await session.execute(select(Service).filter_by(in_panel=panel_code, enable=True))
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting panel services: {e}")
            return []

    async def get_service_by_username_and_panel(self, username: str, panel_code: int):
        """Find service based on username and panel code. Case-sensitive match (mahdie != Mahdie)."""
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service).where(
                        Service.in_panel == panel_code,
                        func.lower(Service.username) == username.lower(),
                    )
                )
                candidates = result.scalars().all()
                for s in candidates:
                    if s.username == username:
                        return True, s
                if candidates:
                    return True, candidates[0]
                return False, "Service not found."
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting service by username and panel: {e}")
            return False, f"Error: {e}"

    async def get_service_and_panel_by_username(self, username: str):
        """Find service and its panel by username in one JOIN (prefer exact case match)."""
        try:
            async with Session() as session:
                result = await session.execute(
                    select(Service, Panels)
                    .join(Panels, Service.in_panel == Panels.code)
                    .where(Service.username == username)
                )
                row = result.first()
                if row:
                    return True, row[0], row[1]

                result = await session.execute(
                    select(Service, Panels)
                    .join(Panels, Service.in_panel == Panels.code)
                    .where(func.lower(Service.username) == username.lower())
                )
                rows = result.all()
                if not rows:
                    return False, None, None
                service, panel = rows[0]
                return True, service, panel
        except SQLAlchemyError as e:
            logger.error("DB Error getting service+panel by username: %s", e)
            return False, None, None

    async def get_services_for_expiration_check_batch(
        self,
        panel_codes: list[int],
        current_time: int,
        expiring_time: int,
        limit: int = 500,
        offset: int = 0,
        *,
        after_expiration_time: int | None = None,
        after_code: int | None = None,
    ):
        """Get services in batches for expiration checking (keyset pagination)."""
        del current_time, offset  # kept for call-site compatibility
        try:
            async with Session() as session:
                filters = [
                    Service.in_panel.in_(panel_codes),
                    Service.expiration_time.isnot(None),
                    Service.expiration_time <= expiring_time,
                ]
                if after_expiration_time is not None and after_code is not None:
                    filters.append(
                        or_(
                            Service.expiration_time > after_expiration_time,
                            and_(
                                Service.expiration_time == after_expiration_time,
                                Service.code > after_code,
                            ),
                        )
                    )
                result = await session.execute(
                    select(Service)
                    .filter(*filters)
                    .order_by(Service.expiration_time.asc(), Service.code.asc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting services for expiration check: {e}")
            return []

    async def get_expired_test_services_batch(
        self,
        panel_codes: list[int],
        current_time: int,
        limit: int = 500,
        offset: int = 0,
        *,
        after_expiration_time: int | None = None,
        after_code: int | None = None,
    ):
        """Get expired test services for immediate cleanup (no 3-day grace)."""
        del offset
        try:
            async with Session() as session:
                filters = [
                    Service.in_panel.in_(panel_codes),
                    Service.is_test == True,  # noqa: E712
                    Service.expiration_time.isnot(None),
                    Service.expiration_time <= current_time,
                ]
                if after_expiration_time is not None and after_code is not None:
                    filters.append(
                        or_(
                            Service.expiration_time > after_expiration_time,
                            and_(
                                Service.expiration_time == after_expiration_time,
                                Service.code > after_code,
                            ),
                        )
                    )
                result = await session.execute(
                    select(Service)
                    .filter(*filters)
                    .order_by(Service.expiration_time.asc(), Service.code.asc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting expired test services: {e}")
            return []

    async def get_services_expired_grace_period_batch(
        self,
        panel_codes: list[int],
        current_time: int,
        limit: int = 500,
        offset: int = 0,
        *,
        after_expiration_time: int | None = None,
        after_code: int | None = None,
    ):
        """Get paid services expired 3+ days ago (grace period ended) for cleanup from DB and panel."""
        del offset
        try:
            async with Session() as session:
                filters = [
                    Service.in_panel.in_(panel_codes),
                    Service.expiration_time.isnot(None),
                    (Service.expiration_time + 259200) <= current_time,
                    or_(Service.is_test.is_(None), Service.is_test == False),  # noqa: E712
                ]
                if after_expiration_time is not None and after_code is not None:
                    filters.append(
                        or_(
                            Service.expiration_time > after_expiration_time,
                            and_(
                                Service.expiration_time == after_expiration_time,
                                Service.code > after_code,
                            ),
                        )
                    )
                result = await session.execute(
                    select(Service)
                    .filter(*filters)
                    .order_by(Service.expiration_time.asc(), Service.code.asc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting services expired grace period: {e}")
            return []

    async def get_all_services_by_panels_batch(
        self,
        panel_codes: list[int],
        limit: int = 500,
        offset: int = 0,
        *,
        after_code: int | None = None,
    ):
        """Get services in batches for low volume check (keyset by code)."""
        del offset
        try:
            async with Session() as session:
                filters = [Service.in_panel.in_(panel_codes)]
                if after_code is not None:
                    filters.append(Service.code > after_code)
                result = await session.execute(
                    select(Service).filter(*filters).order_by(Service.code.asc()).limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"DB Error getting services by panels: {e}")
            return []


async def get_user_services(user_id):

    try:
        user_id = int(user_id)
        async with Session() as session:
            result = await session.execute(select(Service).filter_by(id=user_id))
            return result.scalars().all()
    except (SQLAlchemyError, ValueError) as e:
        return f"Error in fetching user services: {e}"


def _inline_service_search_filter(q: str):
    """Prefix match on service code or config username (fast inline autocomplete)."""
    term = q.strip()
    if not term:
        return None
    if term.isdigit():
        return or_(
            cast(Service.code, String).like(f"{term}%"),
            Service.username.ilike(f"{term}%"),
        )
    return Service.username.ilike(f"{term}%")


async def _paginate_services(*, filters: list, page: int, limit: int) -> tuple[list, int]:
    page = max(1, page)
    limit = min(max(1, limit), 50)
    offset = (page - 1) * limit
    try:
        async with Session() as session:
            stmt = select(Service)
            count_stmt = select(func.count()).select_from(Service)
            if filters:
                cond = and_(*filters)
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)
            total = (await session.execute(count_stmt)).scalar() or 0
            result = await session.execute(
                stmt.order_by(Service.createtime.desc(), Service.code.desc()).limit(limit).offset(offset)
            )
            return list(result.scalars().all()), int(total)
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Error in service pagination: {e}")
        return [], 0


async def get_user_services_paginated(
    user_id: int, page: int = 1, limit: int = 10, search: str | None = None
) -> tuple[list, int]:
    """Get user services with pagination. Search: prefix on code or username."""
    filters = [Service.id == user_id]
    search_filter = _inline_service_search_filter(search) if search else None
    if search_filter is not None:
        filters.append(search_filter)
    return await _paginate_services(filters=filters, page=page, limit=limit)


async def search_services_paginated(
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    owner_user_id: int | None = None,
) -> tuple[list, int]:
    """Admin/global inline search. Optional owner_user_id scopes to one user."""
    filters: list = []
    if owner_user_id is not None:
        filters.append(Service.id == owner_user_id)
    search_filter = _inline_service_search_filter(search) if search else None
    if search_filter is not None:
        filters.append(search_filter)
    return await _paginate_services(filters=filters, page=page, limit=limit)

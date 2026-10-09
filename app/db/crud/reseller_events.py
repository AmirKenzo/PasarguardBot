import json
import time
from typing import Any

from sqlalchemy import delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.reseller_events import ResellerEvent
from app.logger import get_logger

log = get_logger(__name__)


class ResellerEventCRUD:
    async def add_event(
        self,
        *,
        kind: str,
        title: str,
        account_code: int | None = None,
        telegram_id: int | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
        data: dict[str, Any] | None = None,
        reseller_type: str = "panel",
    ) -> bool:
        try:
            async with Session() as session:
                session.add(
                    ResellerEvent(
                        reseller_type=reseller_type,
                        account_code=account_code,
                        telegram_id=telegram_id,
                        kind=kind,
                        title=title[:128],
                        actor_id=actor_id,
                        actor_role=actor_role,
                        data=json.dumps(data, ensure_ascii=False) if data else None,
                        created_at=int(time.time()),
                    )
                )
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to add reseller event: %s", e)
            return False

    async def list_events(
        self,
        *,
        account_code: int | None = None,
        telegram_id: int | None = None,
        kinds: tuple[str, ...] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ResellerEvent], int]:
        """Newest first, optionally scoped to one account or one user. Returns (rows, total)."""
        filters = []
        if account_code is not None:
            filters.append(ResellerEvent.account_code == account_code)
        if telegram_id is not None:
            filters.append(ResellerEvent.telegram_id == telegram_id)
        if kinds:
            filters.append(ResellerEvent.kind.in_(kinds))
        try:
            async with Session() as session:
                total = int(
                    (await session.execute(select(func.count()).select_from(ResellerEvent).where(*filters))).scalar()
                    or 0
                )
                rows = (
                    await session.execute(
                        select(ResellerEvent)
                        .where(*filters)
                        .order_by(ResellerEvent.created_at.desc(), ResellerEvent.id.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                ).scalars()
                return list(rows), total
        except SQLAlchemyError as e:
            log.error("Failed to list reseller events: %s", e)
            return [], 0

    async def delete_events_before(self, cutoff_ts: int) -> int:
        try:
            async with Session() as session:
                result = await session.execute(delete(ResellerEvent).where(ResellerEvent.created_at < cutoff_ts))
                await session.commit()
                return int(result.rowcount or 0)
        except SQLAlchemyError as e:
            log.error("Failed to purge reseller events: %s", e)
            return 0

    @staticmethod
    def load_data(event: ResellerEvent) -> dict[str, Any]:
        if not event.data:
            return {}
        try:
            data = json.loads(event.data)
            return data if isinstance(data, dict) else {}
        except TypeError, json.JSONDecodeError:
            return {}

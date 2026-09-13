"""Audit trail for changes made through the web panel."""

from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import delete, func, select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.panel_audit import PanelAuditLog
from app.logger import get_logger

log = get_logger(__name__)


async def record(
    *,
    admin_id: int | None,
    admin_username: str | None,
    action: str,
    target_type: str | None = None,
    target_id: Any = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """Write one audit row. Never raises — auditing must not break an action."""
    try:
        async with Session() as session:
            session.add(
                PanelAuditLog(
                    admin_id=admin_id,
                    admin_username=(admin_username or "")[:64] or None,
                    action=action[:64],
                    target_type=(target_type or "")[:40] or None,
                    target_id=(str(target_id) if target_id is not None else "")[:64] or None,
                    detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                    ip=(ip or "")[:64] or None,
                    created_at=int(time.time()),
                )
            )
            await session.commit()
    except Exception as exc:
        log.error("panel: could not write the audit entry for %s: %s", action, exc)


async def list_entries(
    *,
    page: int = 1,
    limit: int = 25,
    action: str = "",
    admin_id: int | None = None,
) -> tuple[list[PanelAuditLog], int]:
    """Return one page of audit entries, newest first, plus the total count."""
    offset = (max(1, page) - 1) * limit
    filters = []
    if action:
        filters.append(PanelAuditLog.action == action[:64])
    if admin_id is not None:
        filters.append(PanelAuditLog.admin_id == admin_id)

    async with Session() as session:
        count_stmt = select(func.count()).select_from(PanelAuditLog)
        rows_stmt = select(PanelAuditLog).order_by(PanelAuditLog.id.desc()).limit(limit).offset(offset)
        for condition in filters:
            count_stmt = count_stmt.where(condition)
            rows_stmt = rows_stmt.where(condition)

        total = int((await session.execute(count_stmt)).scalar() or 0)
        rows = (await session.execute(rows_stmt)).scalars().all()
    return list(rows), total


async def known_actions() -> list[str]:
    """Distinct action names, for the filter dropdown."""
    async with Session() as session:
        rows = (await session.execute(select(PanelAuditLog.action).distinct())).scalars().all()
    return sorted(str(row) for row in rows)


async def purge_older_than(days: int) -> int:
    cutoff = int(time.time()) - max(1, days) * 86400
    async with Session() as session:
        result = await session.execute(delete(PanelAuditLog).where(PanelAuditLog.created_at < cutoff))
        await session.commit()
        return int(result.rowcount or 0)

"""Audit log retention: only entries older than the cutoff are removed."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.audit import AuditLog
from app.jobs import audit as audit_job
from app.panel import audit

NOW = 1_800_000_000
DAY = 86400


@pytest.fixture
async def maker(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AuditLog.__table__])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(audit, "Session", session_maker)
    monkeypatch.setattr(audit_job.time, "time", lambda: NOW)
    yield session_maker
    await engine.dispose()


async def test_purge_old_audit_logs_keeps_recent_entries(maker):
    retention = audit_job.AUDIT_LOG_RETENTION_DAYS * DAY
    async with maker() as session:
        session.add_all(
            [
                AuditLog(id=1, action="old", created_at=NOW - retention - 1),
                AuditLog(id=2, action="edge", created_at=NOW - retention),
                AuditLog(id=3, action="recent", created_at=NOW - DAY),
            ]
        )
        await session.commit()

    await audit_job.purge_old_audit_logs()

    async with maker() as session:
        remaining = (await session.execute(select(AuditLog.id).order_by(AuditLog.id))).scalars().all()
    assert remaining == [2, 3]


async def test_purge_before_returns_removed_count(maker):
    async with maker() as session:
        session.add_all([AuditLog(id=i, action="a", created_at=NOW - i) for i in range(1, 4)])
        await session.commit()

    assert await audit.purge_before(NOW - 1) == 2
    assert await audit.purge_before(NOW - 1) == 0

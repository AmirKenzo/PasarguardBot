"""Periodic cleanup of the web panel audit trail so ``audit_logs`` does not grow without bound."""

from __future__ import annotations

import time

from app.logger import LogTag, get_logger
from app.panel.audit import purge_before

logger = get_logger(__name__)

AUDIT_LOG_RETENTION_DAYS = 180


async def purge_old_audit_logs() -> None:
    cutoff = int(time.time()) - AUDIT_LOG_RETENTION_DAYS * 86400
    removed = await purge_before(cutoff)
    if removed:
        logger.info(
            "%s purge_old_audit_logs | removed=%s older_than_days=%s", LogTag.JOB, removed, AUDIT_LOG_RETENTION_DAYS
        )

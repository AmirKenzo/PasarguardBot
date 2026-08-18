"""In-process holding area for a parsed migration preview between upload and confirm.

Parsed data (thousands of rows) is too large/awkward for the Redis step store used
elsewhere, and this is a single-admin, single-session wizard, so a small in-memory
cache keyed by admin id is enough. Only the lightweight step string lives in Redis.
"""

from __future__ import annotations

from app.services.migration.base import ParsedMigration

_pending: dict[int, ParsedMigration] = {}


def set_pending(admin_id: int, parsed: ParsedMigration) -> None:
    _pending[admin_id] = parsed


def get_pending(admin_id: int) -> ParsedMigration | None:
    return _pending.get(admin_id)


def clear_pending(admin_id: int) -> None:
    _pending.pop(admin_id, None)

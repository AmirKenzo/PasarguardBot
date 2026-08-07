"""
Helper functions for webhook handlers.
"""

from app.db.crud.services import ServiceCRUD


async def find_service_by_username(username: str) -> tuple[bool, object | None, object | None]:
    """Find service (+ panel) by username in one JOIN query."""
    return await ServiceCRUD().get_service_and_panel_by_username(username)

"""Panel calls for bot reseller users, all made with the bot's own panel credential."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from httpx import HTTPStatusError
from pasarguard import BulkUsersSelection, PasarguardAPI, UserCreate, UserModify

from app.services.panels.admins import _with_auth_retry
from app.services.panels.auth import fetch_panel_groups_with_auth

BATCH_SIZE = 500
BATCH_SPREAD_SECONDS = 45
MAX_BATCH_PAUSE_SECONDS = 10


def subscription_url(panel, user) -> str:
    url = getattr(user, "subscription_url", None) or ""
    if url and not url.startswith("http"):
        url = f"{panel.base_url}{url}"
    return url


def traffic_counter(user) -> int:
    """The counter billing follows: lifetime traffic (never reset), or used traffic on panels without it."""
    lifetime = int(getattr(user, "lifetime_used_traffic", 0) or 0)
    used = int(getattr(user, "used_traffic", 0) or 0)
    return lifetime if lifetime >= used and lifetime > 0 else used


def expire_timestamp(value: Any) -> int | None:
    if value in (None, 0, ""):
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    try:
        return int(value) or None
    except TypeError, ValueError:
        return None


async def fetch_users(panel, ids: list[int], *, spread: bool = True) -> tuple[dict[int, Any], set[int]]:
    """Read users by id in batches; returns the users found and the ids of batches that failed.

    A user missing from a batch that succeeded no longer exists on the panel. ``spread`` paces the
    batches over the minute (billing); a page request reads them back to back.
    """
    ids = sorted({int(i) for i in ids})
    batches = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    pause = min(MAX_BATCH_PAUSE_SECONDS, BATCH_SPREAD_SECONDS / len(batches)) if spread and len(batches) > 1 else 0
    found: dict[int, Any] = {}
    failed: set[int] = set()
    for index, batch in enumerate(batches):
        if index and pause:
            await asyncio.sleep(pause)

        async def _get(api: PasarguardAPI, token: str, batch=batch):
            return await api.get_users(token=token, ids=batch, limit=len(batch), load_sub=False)

        try:
            resp = await _with_auth_retry(panel, _get)
        except Exception:
            failed.update(batch)
            continue
        for user in resp.users or []:
            found[int(user.id)] = user
    return found, failed


async def create_user(panel, payload: UserCreate):
    return await _with_auth_retry(panel, lambda api, token: api.create_user(user=payload, token=token))


async def get_user(panel, panel_user_id: int):
    """The user, or None when the panel says it does not exist."""
    try:
        return await _with_auth_retry(panel, lambda api, token: api.get_user_by_id(user_id=panel_user_id, token=token))
    except HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def modify_user(panel, panel_user_id: int, payload: UserModify):
    return await _with_auth_retry(
        panel, lambda api, token: api.modify_user_by_id(user_id=panel_user_id, user=payload, token=token)
    )


async def remove_user(panel, panel_user_id: int) -> None:
    try:
        await _with_auth_retry(panel, lambda api, token: api.remove_user_by_id(user_id=panel_user_id, token=token))
    except HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise


async def revoke_subscription(panel, panel_user_id: int):
    return await _with_auth_retry(
        panel, lambda api, token: api.revoke_user_subscription_by_id(user_id=panel_user_id, token=token)
    )


async def reset_usage(panel, panel_user_id: int):
    return await _with_auth_retry(
        panel, lambda api, token: api.reset_user_data_usage_by_id(user_id=panel_user_id, token=token)
    )


async def bulk_set_enabled(panel, panel_user_ids: list[int], *, enabled: bool) -> None:
    ids = sorted({int(i) for i in panel_user_ids})
    for start in range(0, len(ids), BATCH_SIZE):
        selection = BulkUsersSelection(ids=ids[start : start + BATCH_SIZE])
        if enabled:
            await _with_auth_retry(panel, lambda api, token, s=selection: api.bulk_enable_users(bulk=s, token=token))
        else:
            await _with_auth_retry(panel, lambda api, token, s=selection: api.bulk_disable_users(bulk=s, token=token))


async def panel_groups(panel) -> list[dict[str, Any]]:
    resp = await fetch_panel_groups_with_auth(panel)
    return [
        {"id": int(group.id), "name": str(group.name)}
        for group in getattr(resp, "groups", None) or []
        if getattr(group, "id", None) is not None
    ]

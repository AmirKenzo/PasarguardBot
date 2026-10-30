"""Web app panel of a bot reseller: their services, users and usage.

Every call re-checks ownership and limits in ``app.services.bot_reseller.core``; the page only
shows what those rules allow.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter

from app.db.crud.bot_reseller import BotResellerCRUD
from app.db.crud.panels import PanelsManager
from app.db.models.bot_reseller import GRANT_PENDING, BotResellerUser
from app.logger import get_logger
from app.models.webapp.bot_reseller import (
    BotResellerCreateRequest,
    BotResellerEditRequest,
    BotResellerOk,
    BotResellerServiceItem,
    BotResellerStateResponse,
    BotResellerToggleRequest,
    BotResellerUsageResponse,
    BotResellerUsageRow,
    BotResellerUserItem,
    BotResellerUserRequest,
    BotResellerUserResponse,
    BotResellerUsersRequest,
    BotResellerUsersResponse,
)
from app.models.webapp.common import WebAppAuthRequest
from app.routers.webapp.auth import authenticate_user
from app.routers.webapp.errors import internal_error
from app.services.bot_reseller import core, panel as panel_api
from app.telegram.state.lock import acquire_user_lock, release_user_lock

log = get_logger(__name__)
router = APIRouter()

LOCK_BUSY = "درخواست قبلی شما هنوز در حال انجام است."
USAGE_DAYS = 7


async def _user(request: WebAppAuthRequest) -> int:
    user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
    if not user_id:
        raise core.Refused("ورود نامعتبر است.")
    return int(user_id)


async def _run(response_model, call):
    try:
        return await call()
    except (core.Refused, ValueError) as exc:
        return response_model(ok=False, error=str(exc))
    except Exception:
        return response_model(ok=False, error=internal_error(f"bot reseller {response_model.__name__}"))


async def _locked(user_id: int, call):
    """One change at a time per reseller, so two taps can never race on the same user."""
    if not await acquire_user_lock(user_id, "bot_reseller", ttl=60):
        raise core.Refused(LOCK_BUSY)
    try:
        return await call()
    finally:
        await release_user_lock(user_id, "bot_reseller")


def _item(user: BotResellerUser, ctx: core.ResellerContext, panel_user=None) -> BotResellerUserItem:
    service = ctx.services.get(user.service_id)
    terms = ctx.terms(user.service_id)
    item = BotResellerUserItem(
        id=user.id,
        name=user.display_name,
        username=user.username,
        service_id=user.service_id,
        service_name=service.name if service else "-",
        note=user.note,
        disabled_by=user.disabled_by,
        cost=core.user_cost(user, terms.price_per_gb if terms else (service.price_per_gb if service else 0)),
    )
    if panel_user is not None:
        online = getattr(panel_user, "online_at", None)
        item.live = True
        item.status = str(getattr(panel_user, "status", "") or "") or None
        item.used_bytes = int(getattr(panel_user, "used_traffic", 0) or 0)
        item.limit_bytes = int(getattr(panel_user, "data_limit", 0) or 0)
        item.expire = panel_api.expire_timestamp(getattr(panel_user, "expire", None))
        item.online_at = int(online.timestamp()) if online is not None else None
    return item


@router.post("/webapp/bot-reseller/state", response_model=BotResellerStateResponse)
async def bot_reseller_state(request: WebAppAuthRequest) -> BotResellerStateResponse:
    async def call() -> BotResellerStateResponse:
        user_id = await _user(request)
        try:
            ctx = await core.load_context(user_id, require_active_grant=False)
        except core.Refused:
            return BotResellerStateResponse(is_reseller=False)
        crud = BotResellerCRUD()
        since = int(time.time()) - 86400
        balance = (await crud.balances([user_id])).get(user_id, 0)
        counts = await crud.count_users(ctx.reseller.id)
        rows = await crud.usage_rows(ctx.reseller.id, since=since)
        bytes_by_service: dict[int, int] = defaultdict(int)
        amount_24h = 0.0
        for row in rows:
            bytes_by_service[row.service_id] += int(row.bytes or 0)
            amount_24h += float(row.amount or 0)
        burn = amount_24h / 24
        services = []
        for grant in ctx.approved():
            service = ctx.services[grant.service_id]
            terms = core.grant_terms(grant, service)
            services.append(
                BotResellerServiceItem(
                    id=service.id,
                    name=service.name,
                    price_per_gb=terms.price_per_gb,
                    max_users=terms.max_users,
                    max_user_gb=terms.max_user_gb,
                    max_user_days=terms.max_user_days,
                    users=counts.get(service.id, 0),
                    usage_24h_bytes=bytes_by_service.get(service.id, 0),
                )
            )
        pending = [
            ctx.services[g.service_id].name
            for g in ctx.grants
            if g.status == GRANT_PENDING and g.service_id in ctx.services
        ]
        return BotResellerStateResponse(
            is_reseller=bool(services),
            status=ctx.reseller.status,
            balance=balance,
            burn_per_hour=round(burn),
            runway_hours=round(balance / burn, 2) if burn > 0 and balance > 0 else None,
            usage_24h_bytes=sum(bytes_by_service.values()),
            usage_24h_amount=round(amount_24h),
            services=services,
            pending=pending,
            username_prefix=core.affix_value(ctx.reseller.username_prefix, ctx.reseller.telegram_id),
            username_suffix=core.affix_value(ctx.reseller.username_suffix, ctx.reseller.telegram_id),
        )

    return await _run(BotResellerStateResponse, call)


@router.post("/webapp/bot-reseller/users", response_model=BotResellerUsersResponse)
async def bot_reseller_users(request: BotResellerUsersRequest) -> BotResellerUsersResponse:
    async def call() -> BotResellerUsersResponse:
        ctx = await core.load_context(await _user(request))
        users = await BotResellerCRUD().list_users(ctx.reseller.id, service_id=request.service_id)
        by_panel: dict[int, list[BotResellerUser]] = defaultdict(list)
        for user in users:
            by_panel[user.panel_code].append(user)
        live: dict[tuple[int, int], object] = {}
        live_error = False
        for panel_code, panel_users in by_panel.items():
            panel = await PanelsManager().get_panel_by_code(code=panel_code)
            if panel is None:
                live_error = True
                continue
            found, failed = await panel_api.fetch_users(panel, [u.panel_user_id for u in panel_users], spread=False)
            live_error = live_error or bool(failed)
            for panel_user_id, panel_user in found.items():
                live[(panel_code, panel_user_id)] = panel_user
        return BotResellerUsersResponse(
            users=[_item(u, ctx, live.get((u.panel_code, u.panel_user_id))) for u in users],
            live_error=live_error,
        )

    return await _run(BotResellerUsersResponse, call)


@router.post("/webapp/bot-reseller/user", response_model=BotResellerUserResponse)
async def bot_reseller_user(request: BotResellerUserRequest) -> BotResellerUserResponse:
    async def call() -> BotResellerUserResponse:
        ctx = await core.load_context(await _user(request))
        user, panel, panel_user = await core.user_live(ctx, request.id)
        return BotResellerUserResponse(
            user=_item(user, ctx, panel_user),
            subscription_url=panel_api.subscription_url(panel, panel_user) if panel_user else None,
        )

    return await _run(BotResellerUserResponse, call)


@router.post("/webapp/bot-reseller/user/create", response_model=BotResellerUserResponse)
async def bot_reseller_create(request: BotResellerCreateRequest) -> BotResellerUserResponse:
    async def call() -> BotResellerUserResponse:
        user_id = await _user(request)

        async def create() -> BotResellerUserResponse:
            ctx = await core.load_context(user_id)
            row, url = await core.create_user(
                ctx,
                service_id=request.service_id,
                name=request.name,
                gb=request.gb,
                days=request.days,
                note=request.note,
            )
            return BotResellerUserResponse(user=_item(row, ctx), subscription_url=url)

        return await _locked(user_id, create)

    return await _run(BotResellerUserResponse, call)


@router.post("/webapp/bot-reseller/user/edit", response_model=BotResellerOk)
async def bot_reseller_edit(request: BotResellerEditRequest) -> BotResellerOk:
    async def call() -> BotResellerOk:
        user_id = await _user(request)

        async def edit() -> BotResellerOk:
            ctx = await core.load_context(user_id)
            await core.edit_user(ctx, request.id, gb=request.gb, days=request.days, note=request.note)
            return BotResellerOk()

        return await _locked(user_id, edit)

    return await _run(BotResellerOk, call)


@router.post("/webapp/bot-reseller/user/toggle", response_model=BotResellerOk)
async def bot_reseller_toggle(request: BotResellerToggleRequest) -> BotResellerOk:
    async def call() -> BotResellerOk:
        user_id = await _user(request)

        async def toggle() -> BotResellerOk:
            await core.set_user_enabled(await core.load_context(user_id), request.id, enabled=request.enabled)
            return BotResellerOk()

        return await _locked(user_id, toggle)

    return await _run(BotResellerOk, call)


@router.post("/webapp/bot-reseller/user/revoke", response_model=BotResellerUserResponse)
async def bot_reseller_revoke(request: BotResellerUserRequest) -> BotResellerUserResponse:
    async def call() -> BotResellerUserResponse:
        user_id = await _user(request)

        async def revoke() -> BotResellerUserResponse:
            url = await core.revoke_link(await core.load_context(user_id), request.id)
            return BotResellerUserResponse(subscription_url=url)

        return await _locked(user_id, revoke)

    return await _run(BotResellerUserResponse, call)


@router.post("/webapp/bot-reseller/user/reset", response_model=BotResellerOk)
async def bot_reseller_reset(request: BotResellerUserRequest) -> BotResellerOk:
    async def call() -> BotResellerOk:
        user_id = await _user(request)

        async def reset() -> BotResellerOk:
            await core.reset_user_usage(await core.load_context(user_id), request.id)
            return BotResellerOk()

        return await _locked(user_id, reset)

    return await _run(BotResellerOk, call)


@router.post("/webapp/bot-reseller/user/delete", response_model=BotResellerOk)
async def bot_reseller_delete(request: BotResellerUserRequest) -> BotResellerOk:
    async def call() -> BotResellerOk:
        user_id = await _user(request)

        async def delete() -> BotResellerOk:
            await core.delete_user(await core.load_context(user_id), request.id)
            return BotResellerOk()

        return await _locked(user_id, delete)

    return await _run(BotResellerOk, call)


@router.post("/webapp/bot-reseller/usage", response_model=BotResellerUsageResponse)
async def bot_reseller_usage(request: WebAppAuthRequest) -> BotResellerUsageResponse:
    async def call() -> BotResellerUsageResponse:
        ctx = await core.load_context(await _user(request), require_active_grant=False)
        since = int(time.time()) - USAGE_DAYS * 86400
        rows = await BotResellerCRUD().usage_rows(ctx.reseller.id, since=since)
        return BotResellerUsageResponse(
            rows=[
                BotResellerUsageRow(
                    hour=int(row.hour),
                    service_id=int(row.service_id),
                    service_name=ctx.services[row.service_id].name if row.service_id in ctx.services else "-",
                    bytes=int(row.bytes or 0),
                    amount=round(float(row.amount or 0)),
                )
                for row in rows
            ]
        )

    return await _run(BotResellerUsageResponse, call)

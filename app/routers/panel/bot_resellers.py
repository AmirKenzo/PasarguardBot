"""Admin side of bot resellers: services, requests, resellers and their users.

Every change goes through ``app.services.bot_reseller.core`` (the same rules the web app and
the bot use) and is written to the audit log.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Request

from app.db.crud.bot_reseller import BotResellerCRUD, load_group_ids
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.db.models.bot_reseller import GRANT_APPROVED, GRANT_PENDING, BotResellerGrant, BotResellerService
from app.logger import get_logger
from app.models.panel.bot_resellers import (
    BotGrantApproveRequest,
    BotGrantIdRequest,
    BotGrantManualRequest,
    BotGrantRejectRequest,
    BotGrantRow,
    BotGrantTerms,
    BotRequestsResponse,
    BotResellerDetailResponse,
    BotResellerIdRequest,
    BotResellerNamingRequest,
    BotResellerRow,
    BotResellersResponse,
    BotResellerUserIdRequest,
    BotResellerUserRow,
    BotServiceGroup,
    BotServiceGroupsRequest,
    BotServiceGroupsResponse,
    BotServiceRow,
    BotServiceSaveRequest,
    BotServicesResponse,
    BotServiceToggleRequest,
    BotSettings,
    BotSettingsResponse,
    BotSettingsSaveRequest,
)
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.services import PanelPanelOption
from app.panel import audit, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.bot_reseller import core, panel as panel_api

log = get_logger(__name__)
router = APIRouter()

NOT_FOUND = "یافت نشد."


async def _audit(actor: PanelActor, action: str, target_id, detail: dict | None = None) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        target_type="bot_reseller",
        target_id=target_id,
        detail=detail,
        ip=actor.ip,
    )


async def _act(actor: PanelActor, action: str, target_id, call, *, message: str, detail: dict | None = None):
    try:
        result = await call()
    except core.Refused as exc:
        return ActionResponse(ok=False, error=str(exc))
    await _audit(actor, action, target_id, detail)
    return ActionResponse(message=message.format(result=result))


def _service_row(service: BotResellerService, panels: dict[int, str], resellers: int = 0) -> BotServiceRow:
    return BotServiceRow(
        id=service.id,
        panel_code=service.panel_code,
        panel_name=panels.get(service.panel_code),
        name=service.name,
        description=service.description,
        group_ids=load_group_ids(service.group_ids),
        price_per_gb=int(service.price_per_gb or 0),
        sale_enabled=bool(service.sale_enabled),
        max_users=int(service.max_users or 0),
        max_user_gb=float(service.max_user_gb or 0),
        max_user_days=int(service.max_user_days or 0),
        resellers=resellers,
    )


def _grant_row(
    grant: BotResellerGrant,
    service: BotResellerService | None,
    telegram_id: int,
    *,
    users: int = 0,
    balance: int = 0,
) -> BotGrantRow:
    terms = core.grant_terms(grant, service) if service else None
    return BotGrantRow(
        id=grant.id,
        reseller_id=grant.reseller_id,
        telegram_id=telegram_id,
        service_id=grant.service_id,
        service_name=service.name if service else "-",
        status=grant.status,
        price_per_gb=terms.price_per_gb if terms else 0,
        max_users=terms.max_users if terms else 0,
        max_user_gb=terms.max_user_gb if terms else 0,
        max_user_days=terms.max_user_days if terms else 0,
        own_terms=BotGrantTerms(
            price_per_gb=grant.price_per_gb,
            max_users=grant.max_users,
            max_user_gb=grant.max_user_gb,
            max_user_days=grant.max_user_days,
        ),
        users=users,
        balance=balance,
        reject_reason=grant.reject_reason,
        requested_at=int(grant.requested_at),
        decided_at=int(grant.decided_at) if grant.decided_at else None,
    )


@router.post("/panel/bot-resellers/services", response_model=BotServicesResponse)
async def list_services(payload: PanelRequest, request: Request) -> BotServicesResponse:
    async def handle(_: PanelActor) -> BotServicesResponse:
        crud = BotResellerCRUD()
        services = await crud.list_services()
        panels = await queries.panel_names()
        per_service: dict[int, int] = defaultdict(int)
        for grant in await crud.list_grants(status=GRANT_APPROVED):
            per_service[grant.service_id] += 1
        return BotServicesResponse(
            services=[_service_row(s, panels, per_service.get(s.id, 0)) for s in services],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
        )

    return await guard.run(payload, request, BotServicesResponse, handle)


@router.post("/panel/bot-resellers/groups", response_model=BotServiceGroupsResponse)
async def panel_groups(payload: BotServiceGroupsRequest, request: Request) -> BotServiceGroupsResponse:
    async def handle(_: PanelActor) -> BotServiceGroupsResponse:
        panel = await PanelsManager().get_panel_by_code(code=payload.panel_code)
        if panel is None:
            return BotServiceGroupsResponse(ok=False, error="پنل یافت نشد.")
        try:
            groups = await panel_api.panel_groups(panel)
        except Exception as exc:
            log.warning("bot reseller groups fetch failed panel=%s: %s", payload.panel_code, exc)
            return BotServiceGroupsResponse(ok=False, error="گروه‌ها از پنل دریافت نشد؛ اتصال پنل را بررسی کنید.")
        return BotServiceGroupsResponse(groups=[BotServiceGroup(**g) for g in groups])

    return await guard.run(payload, request, BotServiceGroupsResponse, handle)


@router.post("/panel/bot-resellers/settings", response_model=BotSettingsResponse)
async def read_settings(payload: PanelRequest, request: Request) -> BotSettingsResponse:
    async def handle(_: PanelActor) -> BotSettingsResponse:
        setting = await SettingsManager().get_settings()
        services = await BotResellerCRUD().list_services()
        return BotSettingsResponse(
            settings=BotSettings(sale_mode=bool(getattr(setting, "bot_reseller_sale_mode", True))),
            global_sale_mode=bool(setting and setting.sale_mode),
            services_on_sale=sum(1 for service in services if service.sale_enabled),
        )

    return await guard.run(payload, request, BotSettingsResponse, handle)


@router.post("/panel/bot-resellers/settings/save", response_model=ActionResponse)
async def save_settings(payload: BotSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        updates = {"bot_reseller_sale_mode": payload.settings.sale_mode}
        manager = SettingsManager()
        setting = await manager.get_settings()
        if setting is None:
            await manager.add_setting(**updates)
        else:
            await manager.update_setting(setting.id, **updates)
        await _audit(actor, "bot_reseller.settings", None, updates)
        return ActionResponse(message="تنظیمات نمایندگی ربات ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/services/toggle", response_model=ActionResponse)
async def toggle_service(payload: BotServiceToggleRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if not await BotResellerCRUD().set_service_sale(payload.id, payload.sale_enabled):
            return ActionResponse(ok=False, error=NOT_FOUND)
        await _audit(actor, "bot_reseller.service_toggle", payload.id, {"sale_enabled": payload.sale_enabled})
        return ActionResponse(message="فروش سرویس روشن شد." if payload.sale_enabled else "فروش سرویس خاموش شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/services/save", response_model=ActionResponse)
async def save_service(payload: BotServiceSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if not payload.group_ids:
            return ActionResponse(ok=False, error="حداقل یک گروه انتخاب کنید.")
        crud = BotResellerCRUD()
        if payload.id:
            current = await crud.get_service(payload.id)
            if current is None:
                return ActionResponse(ok=False, error=NOT_FOUND)
            if current.panel_code != payload.panel_code:
                return ActionResponse(ok=False, error="پنل سرویس بعد از ساخت قابل تغییر نیست.")
        saved = await crud.save_service(
            payload.id,
            group_ids=payload.group_ids,
            panel_code=payload.panel_code,
            name=payload.name.strip(),
            description=(payload.description or "").strip() or None,
            price_per_gb=payload.price_per_gb,
            sale_enabled=payload.sale_enabled,
            max_users=payload.max_users,
            max_user_gb=payload.max_user_gb,
            max_user_days=payload.max_user_days,
        )
        if saved is None:
            return ActionResponse(ok=False, error="ذخیره سرویس ممکن نشد.")
        await _audit(
            actor, "bot_reseller.service_save", saved.id, payload.model_dump(exclude={"init_data", "session_token"})
        )
        return ActionResponse(message="سرویس ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


async def _grant_rows(grants: list[BotResellerGrant]) -> list[BotGrantRow]:
    crud = BotResellerCRUD()
    services = await crud.get_services(g.service_id for g in grants)
    resellers = {r.id: r for r in await crud.list_resellers(ids={g.reseller_id for g in grants})}
    balances = await crud.balances(r.telegram_id for r in resellers.values())
    rows = []
    for grant in grants:
        reseller = resellers.get(grant.reseller_id)
        if reseller is None:
            continue
        counts = await crud.count_users(reseller.id)
        rows.append(
            _grant_row(
                grant,
                services.get(grant.service_id),
                reseller.telegram_id,
                users=counts.get(grant.service_id, 0),
                balance=balances.get(reseller.telegram_id, 0),
            )
        )
    return rows


@router.post("/panel/bot-resellers/requests", response_model=BotRequestsResponse)
async def list_requests(payload: PanelRequest, request: Request) -> BotRequestsResponse:
    async def handle(_: PanelActor) -> BotRequestsResponse:
        grants = await BotResellerCRUD().list_grants(status=GRANT_PENDING)
        return BotRequestsResponse(requests=await _grant_rows(grants))

    return await guard.run(payload, request, BotRequestsResponse, handle)


@router.post("/panel/bot-resellers/requests/approve", response_model=ActionResponse)
async def approve_request(payload: BotGrantApproveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        terms = payload.terms.model_dump()
        return await _act(
            actor,
            "bot_reseller.approve",
            payload.grant_id,
            lambda: core.approve_grant(payload.grant_id, actor_id=actor.user_id, **terms),
            message="درخواست تأیید شد.",
            detail=terms,
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/requests/reject", response_model=ActionResponse)
async def reject_request(payload: BotGrantRejectRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        return await _act(
            actor,
            "bot_reseller.reject",
            payload.grant_id,
            lambda: core.reject_grant(payload.grant_id, actor_id=actor.user_id, reason=payload.reason),
            message="درخواست رد شد.",
            detail={"reason": payload.reason},
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/grant", response_model=ActionResponse)
async def grant_manually(payload: BotGrantManualRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if await queries.user_balances([payload.telegram_id]) == {}:
            return ActionResponse(ok=False, error="کاربری با این آیدی در ربات نیست.")
        terms = payload.terms.model_dump()
        return await _act(
            actor,
            "bot_reseller.grant",
            payload.telegram_id,
            lambda: core.grant_manually(payload.telegram_id, payload.service_id, actor_id=actor.user_id, **terms),
            message="نمایندگی داده شد.",
            detail={"service_id": payload.service_id, **terms},
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/grant/terms", response_model=ActionResponse)
async def update_grant_terms(payload: BotGrantApproveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        crud = BotResellerCRUD()
        grant = await crud.get_grant(payload.grant_id)
        if grant is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        terms = payload.terms.model_dump()
        if not await crud.update_grant(grant.id, **terms):
            return ActionResponse(ok=False, error="ذخیره ممکن نشد.")
        await _audit(actor, "bot_reseller.terms", grant.id, terms)
        return ActionResponse(message="شرایط ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/grant/revoke", response_model=ActionResponse)
async def revoke_grant(payload: BotGrantIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        return await _act(
            actor,
            "bot_reseller.revoke",
            payload.grant_id,
            lambda: core.revoke_grant(payload.grant_id, actor_id=actor.user_id),
            message="سرویس گرفته شد و {result} یوزر حذف شد.",
        )

    return await guard.run(payload, request, ActionResponse, handle)


async def _reseller_rows(resellers) -> list[BotResellerRow]:
    crud = BotResellerCRUD()
    balances = await crud.balances(r.telegram_id for r in resellers)
    counts = await crud.count_all_users()
    totals = await crud.usage_totals(since=int(time.time()) - 86400)
    grants = await crud.list_grants(status=GRANT_APPROVED)
    services = await crud.get_services(g.service_id for g in grants)
    names: dict[int, list[str]] = defaultdict(list)
    for grant in grants:
        if grant.service_id in services:
            names[grant.reseller_id].append(services[grant.service_id].name)
    rows = []
    for reseller in resellers:
        used, amount = totals.get(reseller.id, (0, 0.0))
        rows.append(
            BotResellerRow(
                id=reseller.id,
                telegram_id=reseller.telegram_id,
                status=reseller.status,
                balance=balances.get(reseller.telegram_id, 0),
                users=counts.get(reseller.id, 0),
                usage_24h_bytes=used,
                usage_24h_amount=round(amount),
                services=names.get(reseller.id, []),
                username_prefix=reseller.username_prefix or "",
                username_suffix=reseller.username_suffix or "",
                created_at=int(reseller.created_at),
            )
        )
    return rows


@router.post("/panel/bot-resellers", response_model=BotResellersResponse)
async def list_resellers(payload: PanelRequest, request: Request) -> BotResellersResponse:
    async def handle(_: PanelActor) -> BotResellersResponse:
        return BotResellersResponse(resellers=await _reseller_rows(await BotResellerCRUD().list_resellers()))

    return await guard.run(payload, request, BotResellersResponse, handle)


@router.post("/panel/bot-resellers/detail", response_model=BotResellerDetailResponse)
async def reseller_detail(payload: BotResellerIdRequest, request: Request) -> BotResellerDetailResponse:
    async def handle(_: PanelActor) -> BotResellerDetailResponse:
        crud = BotResellerCRUD()
        reseller = await crud.get_reseller(payload.id)
        if reseller is None:
            return BotResellerDetailResponse(ok=False, error=NOT_FOUND)
        grants = await crud.list_grants(reseller_id=reseller.id)
        services = await crud.get_services(g.service_id for g in grants)
        prices = await core.prices_for(reseller.id)
        users = await crud.list_users(reseller.id)
        return BotResellerDetailResponse(
            reseller=(await _reseller_rows([reseller]))[0],
            grants=await _grant_rows(grants),
            users=[
                BotResellerUserRow(
                    id=user.id,
                    name=user.display_name,
                    username=user.username,
                    service_name=services[user.service_id].name if user.service_id in services else "-",
                    disabled_by=user.disabled_by,
                    billed_bytes=int(user.baseline_bytes or 0),
                    cost=core.user_cost(user, prices.get(user.service_id, 0)),
                    note=user.note,
                    created_at=int(user.created_at),
                )
                for user in users
            ],
        )

    return await guard.run(payload, request, BotResellerDetailResponse, handle)


@router.post("/panel/bot-resellers/suspend", response_model=ActionResponse)
async def suspend_reseller(payload: BotResellerIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        return await _act(
            actor,
            "bot_reseller.suspend",
            payload.id,
            lambda: core.suspend(payload.id),
            message="نماینده تعلیق شد و {result} یوزر غیرفعال شد.",
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/unsuspend", response_model=ActionResponse)
async def unsuspend_reseller(payload: BotResellerIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        return await _act(
            actor,
            "bot_reseller.unsuspend",
            payload.id,
            lambda: core.unsuspend(payload.id),
            message="تعلیق برداشته شد و {result} یوزر فعال شد.",
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/naming", response_model=ActionResponse)
async def set_reseller_naming(payload: BotResellerNamingRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        return await _act(
            actor,
            "bot_reseller.naming",
            payload.id,
            lambda: core.set_naming(payload.id, payload.username_prefix, payload.username_suffix),
            message="نام‌گذاری یوزرهای جدید ذخیره شد.",
            detail={"prefix": payload.username_prefix, "suffix": payload.username_suffix},
        )

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/bot-resellers/users/delete", response_model=ActionResponse)
async def delete_reseller_user(payload: BotResellerUserIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        crud = BotResellerCRUD()
        user = await crud.get_user(payload.user_id)
        if user is None or user.deleted_at is not None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        reseller = await crud.get_reseller(user.reseller_id)
        if reseller is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        return await _act(
            actor,
            "bot_reseller.user_delete",
            user.id,
            lambda: core.delete_user_by_admin(reseller, user),
            message="یوزر حذف شد.",
            detail={"username": user.username},
        )

    return await guard.run(payload, request, ActionResponse, handle)

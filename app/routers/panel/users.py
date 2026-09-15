"""Bot users: list, detail, balance, block and direct message."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.users import (
    PanelUserBalanceRequest,
    PanelUserBalanceResponse,
    PanelUserBlockRequest,
    PanelUserDetailRequest,
    PanelUserDetailResponse,
    PanelUserMessageRequest,
    PanelUserPhoneRequest,
    PanelUserPhoneResponse,
    PanelUserRow,
    PanelUserServiceRow,
    PanelUsersRequest,
    PanelUsersResponse,
    PanelUserTransactionRow,
)
from app.panel import mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.utils.formatting import normalise_phone_number

router = APIRouter()


def _is_blocked(user) -> bool:
    return (user.status or "") in queries.INACTIVE_STATUSES


def _user_row(user, services: int = 0) -> PanelUserRow:
    return PanelUserRow(
        id=int(user.id),
        status=user.status,
        blocked=_is_blocked(user),
        number=user.number,
        balance=int(user.amount or 0),
        joined_at=int(user.time_s) if user.time_s else None,
        services=services,
    )


@router.post("/panel/users", response_model=PanelUsersResponse)
async def list_users(payload: PanelUsersRequest, request: Request) -> PanelUsersResponse:
    async def handle(_: PanelActor) -> PanelUsersResponse:
        rows, total = await queries.list_users(
            q=payload.q.strip(),
            state=payload.state,
            page=payload.page,
            per_page=payload.limit,
        )
        return PanelUsersResponse(
            users=[_user_row(user) for user in rows],
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelUsersResponse, handle)


@router.post("/panel/users/detail", response_model=PanelUserDetailResponse)
async def user_detail(payload: PanelUserDetailRequest, request: Request) -> PanelUserDetailResponse:
    async def handle(_: PanelActor) -> PanelUserDetailResponse:
        user = await queries.get_user(payload.user_id)
        if user is None:
            return PanelUserDetailResponse(ok=False, error="کاربری با این آیدی پیدا نشد.")

        services, transactions, referrals, panels = await asyncio.gather(
            queries.user_services(payload.user_id),
            queries.user_transactions(payload.user_id),
            queries.user_referrals(payload.user_id),
            queries.panel_names(),
        )
        return PanelUserDetailResponse(
            user=_user_row(user, services=len(services)),
            services=[
                PanelUserServiceRow(
                    code=int(service.code),
                    username=service.username,
                    panel=panels.get(int(service.in_panel or 0)),
                    package_size=service.package_size,
                    expiration_time=service.expiration_time,
                    enable=bool(service.enable),
                    is_test=bool(service.is_test),
                )
                for service in services
            ],
            transactions=[
                PanelUserTransactionRow(
                    id=int(tx.id),
                    amount=int(tx.amount or 0),
                    status=tx.status,
                    created_at=tx.created_at,
                )
                for tx in transactions
            ],
            referrals=referrals,
        )

    return await guard.run(payload, request, PanelUserDetailResponse, handle)


@router.post("/panel/users/balance", response_model=PanelUserBalanceResponse)
async def adjust_balance(payload: PanelUserBalanceRequest, request: Request) -> PanelUserBalanceResponse:
    async def handle(actor: PanelActor) -> PanelUserBalanceResponse:
        if payload.delta == 0:
            return PanelUserBalanceResponse(ok=False, error="مقدار نمی‌تواند صفر باشد.")
        balance = await mutations.adjust_balance(actor, payload.user_id, payload.delta, notify=payload.notify)
        if balance is None:
            return PanelUserBalanceResponse(ok=False, error="کاربری با این آیدی پیدا نشد.")
        return PanelUserBalanceResponse(balance=balance, message="موجودی به‌روزرسانی شد.")

    return await guard.run(payload, request, PanelUserBalanceResponse, handle)


@router.post("/panel/users/block", response_model=ActionResponse)
async def set_block(payload: PanelUserBlockRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.set_user_block(actor, payload.user_id, payload.blocked, notify=payload.notify)
        if not ok:
            return ActionResponse(ok=False, error="کاربری با این آیدی پیدا نشد.")
        return ActionResponse(message="کاربر مسدود شد." if payload.blocked else "مسدودی کاربر برداشته شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/users/phone", response_model=PanelUserPhoneResponse)
async def set_phone(payload: PanelUserPhoneRequest, request: Request) -> PanelUserPhoneResponse:
    async def handle(actor: PanelActor) -> PanelUserPhoneResponse:
        raw = payload.phone.strip()
        # An empty field clears the number rather than failing validation.
        phone = normalise_phone_number(raw) if raw else None
        if raw and not phone:
            return PanelUserPhoneResponse(ok=False, error="فرمت شمارهٔ تلفن معتبر نیست.")
        if not await mutations.set_user_phone(actor, payload.user_id, phone):
            return PanelUserPhoneResponse(ok=False, error="کاربری با این آیدی پیدا نشد.")
        return PanelUserPhoneResponse(
            number=phone,
            message="شماره ثبت شد." if phone else "شماره حذف شد.",
        )

    return await guard.run(payload, request, PanelUserPhoneResponse, handle)


@router.post("/panel/users/message", response_model=ActionResponse)
async def send_message(payload: PanelUserMessageRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        await mutations.send_user_message(actor, payload.user_id, payload.text.strip())
        return ActionResponse(message="پیام ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)

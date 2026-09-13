"""Crypto wallets, manual cards and card-to-card auto-approve rules."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.db.crud.cards import ManualCardManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.wallets import WalletCRUD
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.payments import (
    WALLET_TYPES,
    PanelAutoApproveRuleRow,
    PanelCardActionRequest,
    PanelCardCreateRequest,
    PanelCardRow,
    PanelPaymentsResponse,
    PanelRuleCreateRequest,
    PanelRuleDeleteRequest,
    PanelRuleToggleRequest,
    PanelWalletCreateRequest,
    PanelWalletDeleteRequest,
    PanelWalletRow,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(
        admin_id=actor.user_id,
        admin_username=actor.username,
        action=action,
        ip=actor.ip,
        **kwargs,
    )


@router.post("/panel/payments", response_model=PanelPaymentsResponse)
async def payments_overview(payload: PanelRequest, request: Request) -> PanelPaymentsResponse:
    async def handle(_: PanelActor) -> PanelPaymentsResponse:
        wallets, cards, rules = await asyncio.gather(
            WalletCRUD().get_all_wallets(),
            ManualCardManager().get_all_cards(),
            ManualAutoApproveRuleCRUD().get_all(),
        )
        taken = {str(wallet.type).upper() for wallet in wallets}
        return PanelPaymentsResponse(
            wallets=[
                PanelWalletRow(
                    id=int(wallet.id),
                    type=wallet.type,
                    address=wallet.address,
                    has_api_key=bool(wallet.api_key),
                )
                for wallet in wallets
            ],
            available_wallet_types=[value for value in WALLET_TYPES if value not in taken],
            cards=[
                PanelCardRow(
                    id=int(card.id),
                    number=card.number,
                    name=card.name,
                    active=bool(card.active),
                )
                for card in cards
            ],
            rules=[
                PanelAutoApproveRuleRow(
                    id=int(rule.id),
                    min_successful_tx=int(rule.min_successful_tx or 0),
                    max_successful_tx=rule.max_successful_tx,
                    auto_approve_delay_minutes=int(rule.auto_approve_delay_minutes or 0),
                    is_active=bool(rule.is_active),
                )
                for rule in rules
            ],
        )

    return await guard.run(payload, request, PanelPaymentsResponse, handle)


@router.post("/panel/payments/wallets/create", response_model=ActionResponse)
async def wallet_create(payload: PanelWalletCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        wallet_type = payload.wallet_type.strip().upper()
        if wallet_type not in WALLET_TYPES:
            return ActionResponse(ok=False, error="نوع ارز معتبر نیست.")
        created = await WalletCRUD().create_wallet(
            payload.address.strip(), wallet_type, payload.api_key.strip() or None
        )
        if created is None:
            return ActionResponse(ok=False, error="برای این ارز قبلاً کیف پول ثبت شده است.")
        await _log(actor, "wallet_create", target_type="wallet", target_id=wallet_type)
        return ActionResponse(message="کیف پول اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/wallets/delete", response_model=ActionResponse)
async def wallet_delete(payload: PanelWalletDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await WalletCRUD().delete_wallet(payload.wallet_id)
        await _log(actor, "wallet_delete", target_type="wallet", target_id=payload.wallet_id)
        if not ok:
            return ActionResponse(ok=False, error="کیف پولی با این شناسه پیدا نشد.")
        return ActionResponse(message="کیف پول حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/create", response_model=ActionResponse)
async def card_create(payload: PanelCardCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        number = "".join(ch for ch in payload.number if ch.isdigit())
        if len(number) < 12:
            return ActionResponse(ok=False, error="شمارهٔ کارت معتبر نیست.")
        card = await ManualCardManager().add_card(number, payload.name.strip(), payload.active)
        if card is None:
            return ActionResponse(ok=False, error="کارت ثبت نشد.")
        await _log(actor, "card_create", target_type="manual_card", target_id=number[-4:])
        return ActionResponse(message="کارت اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/activate", response_model=ActionResponse)
async def card_activate(payload: PanelCardActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualCardManager().set_active(payload.card_id)
        await _log(actor, "card_activate", target_type="manual_card", target_id=payload.card_id)
        if not ok:
            return ActionResponse(ok=False, error="کارتی با این شناسه پیدا نشد.")
        return ActionResponse(message="کارت فعال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/cards/delete", response_model=ActionResponse)
async def card_delete(payload: PanelCardActionRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualCardManager().delete_card(payload.card_id)
        await _log(actor, "card_delete", target_type="manual_card", target_id=payload.card_id)
        if not ok:
            return ActionResponse(ok=False, error="کارتی با این شناسه پیدا نشد.")
        return ActionResponse(message="کارت حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/create", response_model=ActionResponse)
async def rule_create(payload: PanelRuleCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        maximum = payload.max_successful_tx
        if maximum is not None and maximum < payload.min_successful_tx:
            return ActionResponse(ok=False, error="حداکثر نمی‌تواند از حداقل کمتر باشد.")
        await ManualAutoApproveRuleCRUD().create(
            min_successful_tx=payload.min_successful_tx,
            max_successful_tx=maximum,
            auto_approve_delay_minutes=payload.auto_approve_delay_minutes,
        )
        await _log(
            actor,
            "auto_approve_rule_create",
            target_type="auto_approve_rule",
            detail={
                "min": payload.min_successful_tx,
                "max": maximum,
                "delay": payload.auto_approve_delay_minutes,
            },
        )
        return ActionResponse(message="قانون اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/toggle", response_model=ActionResponse)
async def rule_toggle(payload: PanelRuleToggleRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        updated = await ManualAutoApproveRuleCRUD().update(payload.rule_id, is_active=payload.is_active)
        await _log(actor, "auto_approve_rule_update", target_type="auto_approve_rule", target_id=payload.rule_id)
        if not updated:
            return ActionResponse(ok=False, error="قانونی با این شناسه پیدا نشد.")
        return ActionResponse(message="وضعیت قانون تغییر کرد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/payments/rules/delete", response_model=ActionResponse)
async def rule_delete(payload: PanelRuleDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ManualAutoApproveRuleCRUD().delete(payload.rule_id)
        await _log(actor, "auto_approve_rule_delete", target_type="auto_approve_rule", target_id=payload.rule_id)
        if not ok:
            return ActionResponse(ok=False, error="قانونی با این شناسه پیدا نشد.")
        return ActionResponse(message="قانون حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

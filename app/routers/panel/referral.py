"""Referral programme: settings and reward history."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.crud.referral import ReferralSettingsCRUD
from app.db.crud.referral_payouts import PAYOUT_PENDING, ReferralPayoutCRUD
from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.marketing import (
    PanelReferralPayoutRow,
    PanelReferralPayoutSettleRequest,
    PanelReferralPayoutsRequest,
    PanelReferralPayoutsResponse,
    PanelReferralRequest,
    PanelReferralResponse,
    PanelReferralRewardRow,
    PanelReferralSaveRequest,
    PanelReferralSettings,
)
from app.panel import audit, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.billing.referral_rewards import SIDE_BONUS, referral_reward_mode, referral_side_mode
from app.telegram.user.referral_earnings.service import notify_user_of_settlement

router = APIRouter()


@router.post("/panel/referral", response_model=PanelReferralResponse)
async def referral_overview(payload: PanelReferralRequest, request: Request) -> PanelReferralResponse:
    async def handle(_: PanelActor) -> PanelReferralResponse:
        settings = await ReferralSettingsCRUD().get_settings()
        rewards, total, paid, bonus = await queries.referral_rewards(page=payload.page, per_page=payload.limit)
        return PanelReferralResponse(
            settings=PanelReferralSettings(
                referral_enabled=bool(getattr(settings, "referral_enabled", True)),
                referral_reward_amount=int(getattr(settings, "referral_reward_amount", 0) or 0),
                referral_reward_mode=referral_reward_mode(settings),
                referral_reward_percent=int(getattr(settings, "referral_reward_percent", 10) or 10),
                referral_reward_max=int(getattr(settings, "referral_reward_max", 0) or 0),
                referral_bonus_mode=referral_side_mode(settings, SIDE_BONUS),
                referral_bonus_percent=int(getattr(settings, "referral_bonus_percent", 5) or 5),
                referral_bonus_max=int(getattr(settings, "referral_bonus_max", 0) or 0),
                referral_reward_destination=(
                    "earnings" if getattr(settings, "referral_reward_destination", "wallet") == "earnings" else "wallet"
                ),
                referral_withdraw_enabled=bool(getattr(settings, "referral_withdraw_enabled", False)),
                referral_withdraw_min=int(getattr(settings, "referral_withdraw_min", 0) or 0),
                referral_transfer_enabled=bool(getattr(settings, "referral_transfer_enabled", True)),
                referral_bonus_amount=int(getattr(settings, "referral_bonus_amount", 0) or 0),
                referral_banner_text=getattr(settings, "referral_banner_text", None),
            ),
            rewards=[
                PanelReferralRewardRow(
                    id=int(item.id),
                    referrer_id=item.referrer_id,
                    referred_id=item.referred_id,
                    reward_amount=int(item.reward_amount or 0),
                    bonus_amount=int(item.bonus_amount or 0),
                    base_amount=item.base_amount,
                    reward_percent=item.reward_percent,
                    bonus_percent=item.bonus_percent,
                    status=item.status,
                    created_at=item.created_at,
                )
                for item in rewards
            ],
            meta=page_meta(total, payload.page, payload.limit),
            total_rewarded=total,
            total_paid=paid,
            total_bonus=bonus,
        )

    return await guard.run(payload, request, PanelReferralResponse, handle)


@router.post("/panel/referral/save", response_model=ActionResponse)
async def save_referral(payload: PanelReferralSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = ReferralSettingsCRUD()
        if await manager.get_settings() is None:
            await manager.create_default_settings()

        updated = await manager.update_settings(
            referral_enabled=payload.referral_enabled,
            referral_reward_amount=payload.referral_reward_amount,
            referral_reward_mode=payload.referral_reward_mode,
            referral_reward_percent=payload.referral_reward_percent,
            referral_reward_max=payload.referral_reward_max,
            referral_bonus_mode=payload.referral_bonus_mode,
            referral_bonus_percent=payload.referral_bonus_percent,
            referral_bonus_max=payload.referral_bonus_max,
            referral_reward_destination=payload.referral_reward_destination,
            referral_withdraw_enabled=payload.referral_withdraw_enabled,
            referral_withdraw_min=payload.referral_withdraw_min,
            referral_transfer_enabled=payload.referral_transfer_enabled,
            referral_bonus_amount=payload.referral_bonus_amount,
            referral_banner_text=payload.referral_banner_text.strip() or None,
        )
        if not updated:
            return ActionResponse(ok=False, error="تنظیمات ذخیره نشد.")

        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="referral_settings_update",
            target_type="referral",
            detail={
                "enabled": payload.referral_enabled,
                "reward": payload.referral_reward_amount,
                "mode": payload.referral_reward_mode,
                "percent": payload.referral_reward_percent,
                "max": payload.referral_reward_max,
                "bonus_mode": payload.referral_bonus_mode,
                "bonus_percent": payload.referral_bonus_percent,
                "bonus_max": payload.referral_bonus_max,
                "destination": payload.referral_reward_destination,
                "withdraw": payload.referral_withdraw_enabled,
                "withdraw_min": payload.referral_withdraw_min,
                "transfer": payload.referral_transfer_enabled,
                "bonus": payload.referral_bonus_amount,
            },
            ip=actor.ip,
        )
        return ActionResponse(message="تنظیمات سیستم دعوت ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/referral/payouts", response_model=PanelReferralPayoutsResponse)
async def referral_payouts(payload: PanelReferralPayoutsRequest, request: Request) -> PanelReferralPayoutsResponse:
    async def handle(_: PanelActor) -> PanelReferralPayoutsResponse:
        crud = ReferralPayoutCRUD()
        rows, total = await crud.list_payouts(status=payload.status or None, page=payload.page, per_page=payload.limit)
        _pending, pending_count = await crud.list_payouts(status=PAYOUT_PENDING, per_page=1)
        return PanelReferralPayoutsResponse(
            payouts=[
                PanelReferralPayoutRow(
                    id=int(row.id),
                    user_id=int(row.user_id),
                    amount=int(row.amount or 0),
                    method=row.method,
                    status=row.status,
                    card_number=row.card_number,
                    card_holder=row.card_holder,
                    admin_id=row.admin_id,
                    admin_note=row.admin_note,
                    created_at=row.created_at,
                    reviewed_at=row.reviewed_at,
                )
                for row in rows
            ],
            meta=page_meta(total, payload.page, payload.limit),
            pending_count=pending_count,
        )

    return await guard.run(payload, request, PanelReferralPayoutsResponse, handle)


@router.post("/panel/referral/payouts/settle", response_model=ActionResponse)
async def settle_referral_payout(payload: PanelReferralPayoutSettleRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        payout, error = await ReferralPayoutCRUD().settle(
            payload.id, admin_id=actor.user_id, paid=payload.paid, note=payload.note.strip() or None
        )
        if payout is None or error:
            return ActionResponse(ok=False, error=error or "درخواست پیدا نشد.")
        await notify_user_of_settlement(payout)
        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="referral_payout_paid" if payload.paid else "referral_payout_rejected",
            target_type="referral_payout",
            target_id=payout.id,
            detail={"user_id": payout.user_id, "amount": payout.amount},
            ip=actor.ip,
        )
        return ActionResponse(
            message="پرداخت ثبت شد." if payload.paid else "درخواست رد شد و مبلغ به درآمد کاربر برگشت."
        )

    return await guard.run(payload, request, ActionResponse, handle)

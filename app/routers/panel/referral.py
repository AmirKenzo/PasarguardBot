"""Referral programme: settings and reward history."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.crud.referral import ReferralSettingsCRUD
from app.models.panel.common import ActionResponse, page_meta
from app.models.panel.marketing import (
    PanelReferralRequest,
    PanelReferralResponse,
    PanelReferralRewardRow,
    PanelReferralSaveRequest,
    PanelReferralSettings,
)
from app.panel import audit, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

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
                "bonus": payload.referral_bonus_amount,
            },
            ip=actor.ip,
        )
        return ActionResponse(message="تنظیمات سیستم دعوت ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)

"""Join-lock channels and log channel destinations."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.db.crud.channels import ChannelManager
from app.db.crud.log_channels import LogChannelManager
from app.logger import LogType
from app.models.panel.channels import (
    DESTINATION_TYPES,
    PanelChannelCreateRequest,
    PanelChannelDeleteRequest,
    PanelChannelRow,
    PanelChannelsResponse,
    PanelLogChannelDeleteRequest,
    PanelLogChannelRow,
    PanelLogChannelSaveRequest,
)
from app.models.panel.common import ActionResponse, PanelRequest
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


@router.post("/panel/channels", response_model=PanelChannelsResponse)
async def channels_overview(payload: PanelRequest, request: Request) -> PanelChannelsResponse:
    async def handle(_: PanelActor) -> PanelChannelsResponse:
        channels, log_channels = await asyncio.gather(
            ChannelManager().get_all_channels(),
            LogChannelManager().get_all_log_channels(),
        )
        return PanelChannelsResponse(
            channels=[
                PanelChannelRow(id=int(channel.id), title=channel.title, link=channel.link) for channel in channels
            ],
            log_channels=[
                PanelLogChannelRow(
                    id=int(item.id),
                    log_type=item.log_type,
                    chat_id=item.chat_id,
                    topic_id=item.topic_id,
                    destination_type=item.destination_type,
                    is_active=bool(item.is_active),
                )
                for item in log_channels
            ],
            log_types=[item.value for item in LogType],
        )

    return await guard.run(payload, request, PanelChannelsResponse, handle)


@router.post("/panel/channels/create", response_model=ActionResponse)
async def channel_create(payload: PanelChannelCreateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        title = payload.title.strip()[:100]
        link = payload.link.strip()[:100]
        if not title or not link:
            return ActionResponse(ok=False, error="عنوان و لینک کانال الزامی است.")
        ok = await ChannelManager().add_or_update_channel(payload.channel_id, link, title)
        await _log(actor, "channel_create", target_type="channel", target_id=payload.channel_id)
        if not ok:
            return ActionResponse(ok=False, error="ثبت کانال انجام نشد.")
        return ActionResponse(message="کانال ثبت شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/channels/delete", response_model=ActionResponse)
async def channel_delete(payload: PanelChannelDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await ChannelManager().delete_channel(payload.channel_id)
        await _log(actor, "channel_delete", target_type="channel", target_id=payload.channel_id)
        if not ok:
            return ActionResponse(ok=False, error="کانالی با این آیدی پیدا نشد.")
        return ActionResponse(message="کانال حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/channels/logs/save", response_model=ActionResponse)
async def log_channel_save(payload: PanelLogChannelSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if payload.log_type not in {item.value for item in LogType}:
            return ActionResponse(ok=False, error="نوع گزارش معتبر نیست.")
        destination = payload.destination_type if payload.destination_type in DESTINATION_TYPES else "channel"

        await LogChannelManager().create_or_update_log_channel(
            log_type=payload.log_type,
            destination_type=destination,
            chat_id=payload.chat_id,
            topic_id=payload.topic_id,
        )
        await _log(
            actor,
            "log_channel_set",
            target_type="log_channel",
            target_id=payload.log_type,
            detail={"chat_id": payload.chat_id, "topic_id": payload.topic_id},
        )
        return ActionResponse(message="مقصد گزارش ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/channels/logs/delete", response_model=ActionResponse)
async def log_channel_delete(payload: PanelLogChannelDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await LogChannelManager().delete_log_channel(payload.log_id)
        await _log(actor, "log_channel_delete", target_type="log_channel", target_id=payload.log_id)
        if not ok:
            return ActionResponse(ok=False, error="مقصدی با این شناسه پیدا نشد.")
        return ActionResponse(message="مقصد گزارش حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

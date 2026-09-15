"""Bot texts: browse the known keys, override them, restore the defaults."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.crud.bot_texts import BotTextCRUD
from app.models.panel.common import ActionResponse
from app.models.panel.texts import (
    BANNER_POSITIONS,
    PanelTextDeleteRequest,
    PanelTextEntry,
    PanelTextSaveRequest,
    PanelTextSection,
    PanelTextsRequest,
    PanelTextsResponse,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.telegram.keyboards.texts import TEXT_KEYS_CONFIG, TEXT_SECTIONS

router = APIRouter()

UNLISTED_SECTION = "unlisted"


def _entry(key: str, definition: dict, row) -> PanelTextEntry:
    return PanelTextEntry(
        key=key,
        title=definition.get("title") or key,
        placeholders=definition.get("placeholders") or {},
        value=row.value if row else None,
        lang=row.lang if row else None,
        banner_url=row.banner_url if row else None,
        banner_position=row.banner_position if row else None,
        stored=row is not None,
    )


def _matches(query: str, key: str, definition: dict, row) -> bool:
    if not query:
        return True
    haystack = " ".join([key, str(definition.get("title") or ""), (row.value if row else "") or ""]).lower()
    return query in haystack


@router.post("/panel/texts", response_model=PanelTextsResponse)
async def list_texts(payload: PanelTextsRequest, request: Request) -> PanelTextsResponse:
    async def handle(_: PanelActor) -> PanelTextsResponse:
        stored = {row.key: row for row in await BotTextCRUD().get_all()}
        query = payload.q.strip().lower()
        known: set[str] = set()
        sections: list[PanelTextSection] = []

        for section, meta in TEXT_SECTIONS.items():
            entries = []
            for definition in TEXT_KEYS_CONFIG.get(section, []):
                key = definition["key"]
                known.add(key)
                row = stored.get(key)
                if _matches(query, key, definition, row):
                    entries.append(_entry(key, definition, row))
            if entries:
                sections.append(
                    PanelTextSection(
                        key=section,
                        name=meta.get("name"),
                        icon=meta.get("icon"),
                        entries=entries,
                    )
                )

        extra = [
            _entry(key, {}, stored[key])
            for key in sorted(stored)
            if key not in known and _matches(query, key, {}, stored[key])
        ]
        if extra:
            sections.append(PanelTextSection(key=UNLISTED_SECTION, entries=extra))

        return PanelTextsResponse(sections=sections)

    return await guard.run(payload, request, PanelTextsResponse, handle)


@router.post("/panel/texts/save", response_model=ActionResponse)
async def save_text(payload: PanelTextSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        key = payload.key.strip()[:100]
        if not key:
            return ActionResponse(ok=False, error="کلید متن الزامی است.")
        position = payload.banner_position if payload.banner_position in BANNER_POSITIONS else ""

        ok = await BotTextCRUD().set_text(
            key=key,
            value=payload.value,
            lang=payload.lang.strip()[:10] or None,
            banner_url=payload.banner_url.strip() or None,
            banner_position=position or None,
        )
        if not ok:
            return ActionResponse(ok=False, error="ذخیرهٔ متن انجام نشد.")

        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="bot_text_update",
            target_type="bot_text",
            target_id=key,
            detail={"length": len(payload.value), "banner": bool(payload.banner_url.strip())},
            ip=actor.ip,
        )
        return ActionResponse(message="متن ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/texts/delete", response_model=ActionResponse)
async def delete_text(payload: PanelTextDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        key = payload.key.strip()[:100]
        if not key:
            return ActionResponse(ok=False, error="کلید متن الزامی است.")
        ok = await BotTextCRUD().delete_text(key, payload.lang.strip()[:10] or None)
        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="bot_text_delete",
            target_type="bot_text",
            target_id=key,
            ip=actor.ip,
        )
        if not ok:
            return ActionResponse(ok=False, error="متن سفارشی برای این کلید ثبت نشده بود.")
        return ActionResponse(message="متن به حالت پیش‌فرض برگشت.")

    return await guard.run(payload, request, ActionResponse, handle)

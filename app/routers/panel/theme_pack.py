"""Theme packs: a library of shareable looks (bot texts, button labels, home layout)."""

from __future__ import annotations

import io

from fastapi import APIRouter, Request

from app import Kenzo
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.theme_pack import (
    ThemePackApplyRequest,
    ThemePackApplyResponse,
    ThemePackCreateRequest,
    ThemePackCurrentRequest,
    ThemePackDetailResponse,
    ThemePackIdRequest,
    ThemePackItem,
    ThemePackOverviewResponse,
    ThemePackPreviewRequest,
    ThemePackPreviewResponse,
    ThemePackSaveRequest,
    ThemePackSaveResponse,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services import theme_pack

router = APIRouter()
log = get_logger(__name__)


def _error(code: str) -> str:
    return theme_pack.error_text(code)


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(actor_id=actor.user_id, actor_username=actor.username, action=action, ip=actor.ip, **kwargs)


def _items(items: list[theme_pack.PackItem]) -> list[ThemePackItem]:
    return [ThemePackItem(**item.public()) for item in items]


async def _resolve_pack(payload: ThemePackPreviewRequest) -> tuple[dict | None, int | None, str | None]:
    """(pack data, library id, error code) for a request naming a library pack or carrying a file."""
    if payload.pack_id is not None:
        found = await theme_pack.get_pack(payload.pack_id)
        if found is None:
            return None, None, "not_found"
        return found[1], payload.pack_id, None
    if payload.pack is not None:
        return payload.pack, None, None
    return None, None, "no_source"


@router.post("/panel/theme-packs", response_model=ThemePackOverviewResponse)
async def overview(payload: PanelRequest, request: Request) -> ThemePackOverviewResponse:
    async def handle(_: PanelActor) -> ThemePackOverviewResponse:
        inventory = await theme_pack.inventory()
        return ThemePackOverviewResponse(packs=await theme_pack.list_packs(), **inventory)

    return await guard.run(payload, request, ThemePackOverviewResponse, handle)


@router.post("/panel/theme-packs/create", response_model=ThemePackSaveResponse)
async def create_from_current(payload: ThemePackCreateRequest, request: Request) -> ThemePackSaveResponse:
    async def handle(actor: PanelActor) -> ThemePackSaveResponse:
        pack = await theme_pack.build_pack(
            name=payload.name,
            text_keys=payload.text_keys,
            button_keys=payload.button_keys,
            include_layout=payload.include_layout,
            include_banners=payload.include_banners,
            include_icons=payload.include_icons,
            include_defaults=payload.include_defaults,
        )
        try:
            result = await theme_pack.save_pack(pack, name=payload.name, actor_id=actor.user_id)
        except theme_pack.PackError as exc:
            return ThemePackSaveResponse(ok=False, error=_error(exc.code))
        if result.error:
            return ThemePackSaveResponse(ok=False, error=_error(result.error))
        await _log(
            actor,
            "theme_pack_create",
            target_type="theme_pack",
            target_id=result.pack_id,
            detail=theme_pack.pack_counts(pack),
        )
        return ThemePackSaveResponse(message="پک ساخته شد.", pack_id=result.pack_id)

    return await guard.run(payload, request, ThemePackSaveResponse, handle)


@router.post("/panel/theme-packs/get", response_model=ThemePackDetailResponse)
async def get_pack(payload: ThemePackIdRequest, request: Request) -> ThemePackDetailResponse:
    async def handle(_: PanelActor) -> ThemePackDetailResponse:
        found = await theme_pack.get_pack(payload.pack_id)
        if found is None:
            return ThemePackDetailResponse(ok=False, error=_error("not_found"))
        entry, data = found
        return ThemePackDetailResponse(pack=entry, data=data, file_name=theme_pack.pack_file_name(entry["name"]))

    return await guard.run(payload, request, ThemePackDetailResponse, handle)


@router.post("/panel/theme-packs/save", response_model=ThemePackSaveResponse)
async def save_pack(payload: ThemePackSaveRequest, request: Request) -> ThemePackSaveResponse:
    async def handle(actor: PanelActor) -> ThemePackSaveResponse:
        try:
            result = await theme_pack.save_pack(
                payload.pack,
                pack_id=payload.pack_id,
                name=payload.name,
                actor_id=actor.user_id,
                strict=payload.strict,
            )
        except theme_pack.PackError as exc:
            return ThemePackSaveResponse(ok=False, error=_error(exc.code))
        dropped = _items(result.dropped)
        if result.error:
            return ThemePackSaveResponse(ok=False, error=_error(result.error), dropped=dropped)
        await _log(
            actor,
            "theme_pack_update" if payload.pack_id else "theme_pack_import",
            target_type="theme_pack",
            target_id=result.pack_id,
            detail={"dropped": len(dropped)},
        )
        return ThemePackSaveResponse(message="پک ذخیره شد.", pack_id=result.pack_id, dropped=dropped)

    return await guard.run(payload, request, ThemePackSaveResponse, handle)


@router.post("/panel/theme-packs/delete", response_model=ActionResponse)
async def delete_pack(payload: ThemePackIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if not await theme_pack.delete_pack(payload.pack_id):
            return ActionResponse(ok=False, error=_error("not_found"))
        await _log(actor, "theme_pack_delete", target_type="theme_pack", target_id=payload.pack_id)
        return ActionResponse(message="پک حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/theme-packs/send", response_model=ActionResponse)
async def send_pack(payload: ThemePackIdRequest, request: Request) -> ActionResponse:
    """Send a library pack as a file to the admin's private chat, ready to forward to someone."""

    async def handle(actor: PanelActor) -> ActionResponse:
        found = await theme_pack.get_pack(payload.pack_id)
        if found is None:
            return ActionResponse(ok=False, error=_error("not_found"))
        if not Kenzo.is_connected():
            return ActionResponse(ok=False, error="ربات به تلگرام متصل نیست.")
        entry, data = found
        document = io.BytesIO(theme_pack.pack_to_json(data).encode("utf-8"))
        document.name = theme_pack.pack_file_name(entry["name"])
        caption = theme_pack.share_caption(entry)
        try:
            await Kenzo.send_file(actor.user_id, document, caption=caption, force_document=True)
        except Exception as exc:
            log.error("panel: theme pack delivery failed: %s", exc, exc_info=True)
            return ActionResponse(ok=False, error="ارسال فایل پک انجام نشد.")
        await _log(actor, "theme_pack_send", target_type="theme_pack", target_id=payload.pack_id)
        return ActionResponse(message="فایل پک در چت خصوصی ربات برایت ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/theme-packs/preview", response_model=ThemePackPreviewResponse)
async def preview(payload: ThemePackPreviewRequest, request: Request) -> ThemePackPreviewResponse:
    async def handle(_: PanelActor) -> ThemePackPreviewResponse:
        data, _pack_id, error = await _resolve_pack(payload)
        if error:
            return ThemePackPreviewResponse(ok=False, error=_error(error))
        try:
            parsed = await theme_pack.preview(data)
        except theme_pack.PackError as exc:
            return ThemePackPreviewResponse(ok=False, error=_error(exc.code))
        return ThemePackPreviewResponse(name=parsed.name, source=parsed.source, items=_items(parsed.items))

    return await guard.run(payload, request, ThemePackPreviewResponse, handle)


@router.post("/panel/theme-packs/apply", response_model=ThemePackApplyResponse)
async def apply(payload: ThemePackApplyRequest, request: Request) -> ThemePackApplyResponse:
    async def handle(actor: PanelActor) -> ThemePackApplyResponse:
        if payload.mode not in theme_pack.APPLY_MODES:
            return ThemePackApplyResponse(ok=False, error=_error("bad_mode"))
        data, pack_id, error = await _resolve_pack(payload)
        if error:
            return ThemePackApplyResponse(ok=False, error=_error(error))
        try:
            result = await theme_pack.apply(
                data, payload.item_ids, actor_id=actor.user_id, mode=payload.mode, pack_id=pack_id
            )
        except theme_pack.PackError as exc:
            return ThemePackApplyResponse(ok=False, error=_error(exc.code))
        if result.import_id is None:
            return ThemePackApplyResponse(message="چیزی برای اعمال نبود؛ ربات همین حالا همین شکل را دارد.")
        await _log(
            actor,
            "theme_pack_apply",
            target_type="theme_pack",
            target_id=pack_id,
            detail={
                "import_id": result.import_id,
                "mode": payload.mode,
                "texts": result.texts,
                "buttons": result.buttons,
                "layout": result.layout,
                "reset": result.reset,
            },
        )
        return ThemePackApplyResponse(
            message="پک اعمال شد.", applied=result.applied, reset=result.reset, import_id=result.import_id
        )

    return await guard.run(payload, request, ThemePackApplyResponse, handle)


@router.post("/panel/theme-packs/undo", response_model=ActionResponse)
async def undo(payload: PanelRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        import_id = await theme_pack.undo_last_import()
        if import_id is None:
            return ActionResponse(ok=False, error="اعمال پکی برای برگرداندن وجود ندارد.")
        await _log(actor, "theme_pack_undo", target_type="theme_pack", target_id=import_id)
        return ActionResponse(message="وضعیت قبل از آخرین اعمال پک برگردانده شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/theme-packs/current", response_model=ThemePackDetailResponse)
async def current_values(payload: ThemePackCurrentRequest, request: Request) -> ThemePackDetailResponse:
    async def handle(_: PanelActor) -> ThemePackDetailResponse:
        # include_defaults: a key the admin never customized still gets its built-in text to start from.
        data = await theme_pack.build_pack(
            text_keys=payload.text_keys,
            button_keys=payload.button_keys,
            include_layout=payload.include_layout,
            include_defaults=True,
        )
        return ThemePackDetailResponse(data=data)

    return await guard.run(payload, request, ThemePackDetailResponse, handle)

"""Help menu buttons: link / download-app / text buttons, their layout, release files and stored versions."""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, Request

from app.db.crud.app_files import AppFileManager
from app.db.crud.help_buttons import HelpButtonCRUD, HelpDownloadAppCRUD
from app.db.crud.log_channels import LogChannelManager
from app.db.crud.settings import SettingsManager
from app.db.models.help_buttons import HelpButton
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.help_buttons import (
    HELP_STYLE_OPTIONS,
    PanelHelpButton,
    PanelHelpButtonIdRequest,
    PanelHelpButtonSaveRequest,
    PanelHelpButtonSaveResponse,
    PanelHelpButtonsResponse,
    PanelHelpLayoutRequest,
    PanelHelpPreset,
    PanelHelpPresetsRequest,
    PanelHelpReleaseFile,
    PanelHelpReleaseRequest,
    PanelHelpReleaseResponse,
    PanelHelpSync,
    PanelHelpTarget,
    PanelHelpVersion,
    PanelHelpVersionDeleteRequest,
    PanelHelpVersionsResponse,
)
from app.panel import audit
from app.panel.forms import parse_icon
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.telegram.shared.utils.help_download import (
    LEGACY_APPS,
    fetch_latest_release_assets,
    get_download_targets,
    matches_file_pattern,
    new_target_id,
    normalize_target,
    normalize_targets,
    run_admin_app_files_sync,
)

router = APIRouter()
log = get_logger(__name__)

URL_PREFIXES = ("http://", "https://", "tg://")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}/[A-Za-z0-9_.-]{1,120}$")
NO_VERSION_TAG = "بدون نسخه"
RELEASE_CACHE_TTL = 300
_release_cache: dict[str, tuple[float, str, list[dict]]] = {}
_sync_state: dict[str, Any] = {"running": False, "summary": None, "task": None}


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(actor_id=actor.user_id, actor_username=actor.username, action=action, ip=actor.ip, **kwargs)


def _kind(btn: HelpButton) -> str:
    if not btn.callback_key:
        return "link"
    if btn.repo_owner or btn.repo_name:
        return "app"
    return "text"


def _target_out(target: dict) -> PanelHelpTarget:
    icon = target.get("button_icon")
    return PanelHelpTarget(
        id=target["id"],
        button_text=target.get("button_text") or "",
        button_style=target.get("button_style") or None,
        button_icon=str(icon) if icon is not None else None,
        patterns=list(target.get("patterns") or []),
    )


def _button_out(btn: HelpButton) -> PanelHelpButton:
    kind = _kind(btn)
    repo = f"{btn.repo_owner or ''}/{btn.repo_name or ''}" if kind == "app" else None
    return PanelHelpButton(
        id=btn.id,
        number=btn.button_number,
        kind=kind,
        text=(btn.button_text or "").strip(),
        style=btn.button_style or None,
        icon=btn.button_icon,
        url=btn.button_url if kind == "link" else None,
        callback_key=btn.callback_key,
        repo=repo,
        ios_url=btn.ios_url,
        targets=[_target_out(t) for t in get_download_targets(btn)] if kind == "app" else [],
        legacy_categories=kind == "app" and not normalize_targets(btn.download_targets) and bool(btn.categories),
        custom_message=btn.custom_message if kind == "text" else None,
    )


def _layout_of(buttons: list[HelpButton]) -> list[list[int]]:
    """Consecutive button numbers share a row, a gap starts a new one (same rule as the bot)."""
    rows: list[list[int]] = []
    prev: int | None = None
    for btn in sorted(buttons, key=lambda b: b.button_number):
        if prev is None or btn.button_number != prev + 1:
            rows.append([])
        rows[-1].append(btn.id)
        prev = btn.button_number
    return rows


async def _sync_state_out() -> PanelHelpSync:
    destination = await LogChannelManager().get_log_channel_destination("app_files")
    return PanelHelpSync(
        running=bool(_sync_state["running"]),
        last_summary=_sync_state["summary"],
        log_channel_set=bool(destination),
    )


def _style_value(raw: str | None) -> str:
    """Stored colour: empty means no colour."""
    value = (raw or "").strip()
    return value if value in HELP_STYLE_OPTIONS and value != "none" else ""


def _normalize_url(raw: str) -> str | None:
    url = (raw or "").strip()
    if url.startswith("t.me/"):
        url = "https://" + url
    return url if url.startswith(URL_PREFIXES) and len(url) > 8 else None


def _clean_targets(targets: list[PanelHelpTarget]) -> list[dict] | str:
    """Validated targets for storage, or an error message."""
    cleaned: list[dict] = []
    seen: set[str] = set()
    for index, target in enumerate(targets):
        text = target.button_text.strip()
        if not text:
            return f"متن دکمهٔ دانلود شمارهٔ {index + 1} خالی است."
        patterns = [p.strip() for p in target.patterns if p.strip()]
        if not patterns:
            return f"دکمهٔ دانلود «{text}» هیچ الگویی ندارد."
        try:
            icon = parse_icon(target.button_icon or "")
        except ValueError:
            return f"آیدی ایموجی دکمهٔ «{text}» معتبر نیست."
        target_id = re.sub(r"[^A-Za-z0-9]", "", target.id or "")[:8]
        if not target_id or target_id in seen:
            target_id = new_target_id()
        seen.add(target_id)
        cleaned.append(
            normalize_target(
                {
                    "id": target_id,
                    "button_text": text,
                    "button_style": _style_value(target.button_style) or None,
                    "button_icon": icon,
                    "patterns": patterns,
                },
                index,
            )
        )
    return cleaned


async def _new_callback_key(text: str) -> str:
    """ASCII key without underscores, so ``Download_<key>_t_<id>`` stays parseable and under 64 bytes."""
    crud = HelpDownloadAppCRUD()
    base = re.sub(r"[^a-z0-9]", "", text.lower())[:24] or f"app{secrets.token_hex(3)}"
    key = base
    while await crud.get_by_callback_key(key):
        key = f"{base}{secrets.token_hex(2)}"
    return key


async def _release(repo: str, refresh: bool) -> tuple[str, list[dict]] | None:
    cache_key = repo.lower()
    cached = _release_cache.get(cache_key)
    if cached and not refresh and time.monotonic() - cached[0] < RELEASE_CACHE_TTL:
        return cached[1], cached[2]
    owner, name = repo.split("/", 1)
    result = await fetch_latest_release_assets(owner, name)
    if result is None:
        return None
    _release_cache[cache_key] = (time.monotonic(), result[0], result[1])
    return result


@router.post("/panel/help-buttons", response_model=PanelHelpButtonsResponse)
async def help_buttons_overview(payload: PanelRequest, request: Request) -> PanelHelpButtonsResponse:
    async def handle(_: PanelActor) -> PanelHelpButtonsResponse:
        buttons, sync, setting = await asyncio.gather(
            HelpButtonCRUD().get_all_buttons(),
            _sync_state_out(),
            SettingsManager().get_settings(),
        )
        existing_keys = {(b.callback_key or "").lower() for b in buttons}
        presets = [
            PanelHelpPreset(
                key=key,
                name=app.get("display_name", key),
                repo=f"{app['repo_owner']}/{app['repo_name']}",
            )
            for key, app in LEGACY_APPS.items()
            if key.lower() not in existing_keys
        ]
        return PanelHelpButtonsResponse(
            buttons=[_button_out(b) for b in buttons],
            layout=_layout_of(buttons),
            presets=presets,
            sync=sync,
            premium_emoji_enabled=bool(getattr(setting, "premium_emoji_status", False)) if setting else False,
        )

    return await guard.run(payload, request, PanelHelpButtonsResponse, handle)


@router.post("/panel/help-buttons/layout", response_model=ActionResponse)
async def save_help_layout(payload: PanelHelpLayoutRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if any(len(row) > 8 for row in payload.layout):
            return ActionResponse(ok=False, error="هر ردیف حداکثر ۸ دکمه می‌تواند داشته باشد.")
        rows = [row for row in payload.layout if row]
        ok = await HelpButtonCRUD().apply_layout(rows)
        await _log(actor, "help_layout_update", target_type="help_buttons", detail={"rows": len(rows)})
        if not ok:
            return ActionResponse(ok=False, error="ذخیرهٔ چیدمان انجام نشد.")
        return ActionResponse(message="چیدمان راهنما ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/help-buttons/save", response_model=PanelHelpButtonSaveResponse)
async def save_help_button(payload: PanelHelpButtonSaveRequest, request: Request) -> PanelHelpButtonSaveResponse:
    async def handle(actor: PanelActor) -> PanelHelpButtonSaveResponse:
        def fail(message: str) -> PanelHelpButtonSaveResponse:
            return PanelHelpButtonSaveResponse(ok=False, error=message)

        text = payload.text.strip()
        if not text:
            return fail("متن دکمه الزامی است.")
        style = _style_value(payload.style)
        try:
            icon = parse_icon(payload.icon)
        except ValueError:
            return fail("آیدی ایموجی معتبر نیست.")

        existing: HelpButton | None = None
        if payload.id is not None:
            existing = await HelpButtonCRUD().get_by_id(payload.id)
            if existing is None:
                return fail("دکمه پیدا نشد.")
            if _kind(existing) != payload.kind:
                return fail("نوع دکمه قابل تغییر نیست؛ یک دکمهٔ جدید بسازید.")

        link_crud = HelpButtonCRUD()
        app_crud = HelpDownloadAppCRUD()
        button_id: int | None = existing.id if existing else None

        if payload.kind == "link":
            url = _normalize_url(payload.url)
            if not url:
                return fail("لینک باید با https://، http://، tg:// یا t.me/ شروع شود.")
            number = existing.button_number if existing else await link_crud.next_row_number()
            ok = await link_crud.set_button(
                number,
                button_text=text,
                button_url=url,
                button_style=style,
                button_icon=icon,
                clear_icon=icon is None,
            )
            if not ok:
                return fail("ذخیرهٔ دکمه انجام نشد.")
            if button_id is None:
                created = await link_crud.get_button(number)
                button_id = created.id if created else None

        elif payload.kind == "app":
            repo = payload.repo.strip().removeprefix("https://github.com/").strip("/")
            if not REPO_RE.match(repo):
                return fail("مخزن GitHub باید به شکل owner/repo باشد.")
            owner, name = repo.split("/", 1)
            ios_url = ""
            if payload.ios_url.strip():
                ios_url = _normalize_url(payload.ios_url) or ""
                if not ios_url:
                    return fail("لینک iOS معتبر نیست.")
            targets = _clean_targets(payload.targets)
            if isinstance(targets, str):
                return fail(targets)
            if existing is None:
                number = await link_crud.next_row_number()
                created = await app_crud.create(
                    button_text=text,
                    callback_key=await _new_callback_key(text),
                    repo_owner=owner,
                    repo_name=name,
                    categories={},
                    ios_url=ios_url or None,
                    download_targets=targets,
                )
                if created is None:
                    return fail("ساخت اپ انجام نشد.")
                button_id = created.id
                await link_crud.set_button_number(button_id, number)
            ok = await app_crud.update(
                button_id,
                button_text=text,
                repo_owner=owner,
                repo_name=name,
                ios_url=ios_url,
                download_targets=targets,
                button_style=style,
                button_icon=icon,
                clear_icon=icon is None,
            )
            if not ok:
                return fail("ذخیرهٔ اپ انجام نشد.")

        else:
            message = payload.custom_message.strip()
            if not message:
                return fail("متن پیام الزامی است.")
            if existing is None:
                number = await link_crud.next_row_number()
                created = await app_crud.create_text_only(
                    button_text=text, callback_key=await _new_callback_key(text), custom_message=message
                )
                if created is None:
                    return fail("ساخت دکمه انجام نشد.")
                button_id = created.id
                await link_crud.set_button_number(button_id, number)
            ok = await app_crud.update(
                button_id,
                button_text=text,
                custom_message=message,
                button_style=style,
                button_icon=icon,
                clear_icon=icon is None,
            )
            if not ok:
                return fail("ذخیرهٔ دکمه انجام نشد.")

        await _log(
            actor,
            "help_button_create" if existing is None else "help_button_update",
            target_type="help_button",
            target_id=str(button_id),
            detail={"kind": payload.kind, "text": text},
        )
        return PanelHelpButtonSaveResponse(id=button_id, message="دکمه ذخیره شد.")

    return await guard.run(payload, request, PanelHelpButtonSaveResponse, handle)


@router.post("/panel/help-buttons/delete", response_model=ActionResponse)
async def delete_help_button(payload: PanelHelpButtonIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        btn = await HelpButtonCRUD().get_by_id(payload.id)
        if btn is None:
            return ActionResponse(ok=False, error="دکمه پیدا نشد.")
        if btn.callback_key:
            ok = await HelpDownloadAppCRUD().delete(btn.id)
        else:
            ok = await HelpButtonCRUD().delete_button(btn.button_number)
        await _log(
            actor,
            "help_button_delete",
            target_type="help_button",
            target_id=str(btn.id),
            detail={"text": btn.button_text},
        )
        if not ok:
            return ActionResponse(ok=False, error="حذف دکمه انجام نشد.")
        return ActionResponse(message="دکمه حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/help-buttons/presets", response_model=ActionResponse)
async def add_help_presets(payload: PanelHelpPresetsRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        app_crud = HelpDownloadAppCRUD()
        link_crud = HelpButtonCRUD()
        wanted = {key.lower() for key in payload.keys}
        added = 0
        for key, app in LEGACY_APPS.items():
            callback_key = key.lower()
            if callback_key not in wanted or await app_crud.get_by_callback_key(callback_key):
                continue
            number = await link_crud.next_row_number()
            created = await app_crud.create(
                button_text=app.get("display_name", key),
                callback_key=callback_key,
                repo_owner=app["repo_owner"],
                repo_name=app["repo_name"],
                categories=app.get("categories", {}),
                default_file=app.get("default_file"),
            )
            if created is None:
                continue
            await link_crud.set_button_number(created.id, number)
            added += 1
        await _log(actor, "help_presets_add", target_type="help_buttons", detail={"added": added})
        if not added:
            return ActionResponse(ok=False, error="اپی اضافه نشد.")
        return ActionResponse(message=f"{added} اپ اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/help-buttons/release", response_model=PanelHelpReleaseResponse)
async def help_release_files(payload: PanelHelpReleaseRequest, request: Request) -> PanelHelpReleaseResponse:
    async def handle(_: PanelActor) -> PanelHelpReleaseResponse:
        repo = payload.repo.strip().removeprefix("https://github.com/").strip("/")
        if not REPO_RE.match(repo):
            return PanelHelpReleaseResponse(ok=False, error="مخزن GitHub باید به شکل owner/repo باشد.")
        release = await _release(repo, payload.refresh)
        if release is None:
            return PanelHelpReleaseResponse(ok=False, error="آخرین ریلیز این مخزن از GitHub خوانده نشد.")
        tag, assets = release

        targets = [(t.id, [p.strip() for p in t.patterns if p.strip()]) for t in payload.targets]
        matches = {target_id: 0 for target_id, _ in targets}
        files: list[PanelHelpReleaseFile] = []
        for asset in assets:
            name = asset.get("name") or ""
            if not name:
                continue
            owner: str | None = None
            for target_id, patterns in targets:
                if any(matches_file_pattern(name, p) for p in patterns):
                    matches[target_id] += 1
                    owner = owner or target_id
            files.append(
                PanelHelpReleaseFile(
                    name=name, size_mb=round((asset.get("size") or 0) / (1024 * 1024), 2), target_id=owner
                )
            )
        return PanelHelpReleaseResponse(tag=tag, files=files, matches=matches)

    return await guard.run(payload, request, PanelHelpReleaseResponse, handle)


async def _run_sync() -> None:
    class _Status:
        async def edit(self, text: str, *args, **kwargs) -> None:
            _sync_state["summary"] = text

    try:
        await run_admin_app_files_sync(_Status())
    except Exception as exc:
        log.error("panel: help app files sync failed: %s", exc, exc_info=True)
        _sync_state["summary"] = "❌ بروزرسانی با خطا متوقف شد."
    finally:
        _sync_state["running"] = False


@router.post("/panel/help-buttons/sync", response_model=ActionResponse)
async def run_help_sync(payload: PanelRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if _sync_state["running"]:
            return ActionResponse(ok=False, error="یک بروزرسانی در حال اجراست.")
        if not await LogChannelManager().get_log_channel_destination("app_files"):
            return ActionResponse(ok=False, error="اول کانال لاگ «فایل‌های برنامه» را در بخش کانال‌ها تنظیم کنید.")
        _sync_state["running"] = True
        _sync_state["summary"] = None
        _sync_state["task"] = asyncio.create_task(_run_sync())
        await _log(actor, "help_sync_run", target_type="help_buttons")
        return ActionResponse(message="بروزرسانی شروع شد.")

    return await guard.run(payload, request, ActionResponse, handle)


async def _app_or_none(app_id: int) -> HelpButton | None:
    app = await HelpDownloadAppCRUD().get_by_id(app_id)
    return app if app is not None and app.callback_key else None


@router.post("/panel/help-buttons/versions", response_model=PanelHelpVersionsResponse)
async def help_versions(payload: PanelHelpButtonIdRequest, request: Request) -> PanelHelpVersionsResponse:
    async def handle(_: PanelActor) -> PanelHelpVersionsResponse:
        app = await _app_or_none(payload.id)
        if app is None:
            return PanelHelpVersionsResponse(ok=False, error="اپ پیدا نشد.")
        grouped: dict[str, list[str]] = {}
        for record in await AppFileManager().get_app_files_by_key(app.callback_key):
            grouped.setdefault(record.tag_name or NO_VERSION_TAG, []).append(record.file_name)
        return PanelHelpVersionsResponse(
            versions=[PanelHelpVersion(tag=tag, count=len(names), files=names) for tag, names in grouped.items()]
        )

    return await guard.run(payload, request, PanelHelpVersionsResponse, handle)


@router.post("/panel/help-buttons/versions/delete", response_model=ActionResponse)
async def delete_help_version(payload: PanelHelpVersionDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        app = await _app_or_none(payload.id)
        if app is None:
            return ActionResponse(ok=False, error="اپ پیدا نشد.")
        manager = AppFileManager()
        tag = payload.tag.strip()
        if not tag:
            deleted = await manager.delete_app_files_by_key(app.callback_key)
        else:
            deleted = 0
            for record in await manager.get_app_files_by_key(app.callback_key):
                if (record.tag_name or NO_VERSION_TAG) == tag and await manager.delete_app_file(record.id):
                    deleted += 1
        await _log(
            actor,
            "help_versions_delete",
            target_type="help_button",
            target_id=str(app.id),
            detail={"tag": tag or "*", "deleted": deleted},
        )
        return ActionResponse(message=f"{deleted} فایل حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

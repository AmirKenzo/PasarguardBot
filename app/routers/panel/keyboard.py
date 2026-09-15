"""Keyboard layout, button text/colour and premium emoji icons."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.keyboard import (
    OTHER_SECTION,
    SECTION_PREFIXES,
    STYLE_OPTIONS,
    PanelKeyboardButton,
    PanelKeyboardButtonSaveRequest,
    PanelKeyboardIconClearRequest,
    PanelKeyboardLayoutRequest,
    PanelKeyboardResponse,
)
from app.panel import audit
from app.panel.forms import parse_icon
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.keyboard_glass import GLASS_KEY_PREFIX, glass_mode_active
from app.telegram.keyboards.home import DEFAULT_HOME_LAYOUT, home_button_conditions
from app.telegram.keyboards.registry import (
    KEYBOARD_BUTTON_DEFAULT_STYLES,
    KEYBOARD_BUTTON_DEFAULTS,
    KEYBOARD_BUTTON_TITLES,
)
from app.utils.text.glass import GLASS_STYLE, glass_text, unglass_text

router = APIRouter()

HOME_KEYS = tuple(key for row in DEFAULT_HOME_LAYOUT for key in row)
SECTION_SLUGS = [slug for _prefix, slug in SECTION_PREFIXES] + [OTHER_SECTION]


def _section_of(key: str) -> str:
    for prefix, slug in SECTION_PREFIXES:
        if key.startswith(prefix):
            return slug
    return OTHER_SECTION


def _default_text(key: str) -> str:
    return KEYBOARD_BUTTON_DEFAULTS.get(key, KEYBOARD_BUTTON_TITLES.get(key, key))


def _current_layout(buttons: dict) -> list[list[str]]:
    """Rebuild the saved layout, falling back to the bot's default."""
    placed = [(row.sort_row, row.sort_order or 0, key) for key, row in buttons.items() if row.sort_row is not None]
    if not placed:
        return [list(row) for row in DEFAULT_HOME_LAYOUT]
    rows: dict[int, list[tuple[int, str]]] = {}
    for row_index, order, key in placed:
        rows.setdefault(int(row_index), []).append((int(order), key))
    layout = [[key for _, key in sorted(items)] for _, items in sorted(rows.items())]
    # any home button the admin never placed goes to its own trailing row
    seen = {key for row in layout for key in row}
    layout.extend([key] for key in HOME_KEYS if key not in seen)
    return layout


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        ip=actor.ip,
        **kwargs,
    )


@router.post("/panel/keyboard", response_model=PanelKeyboardResponse)
async def keyboard_overview(payload: PanelRequest, request: Request) -> PanelKeyboardResponse:
    async def handle(_: PanelActor) -> PanelKeyboardResponse:
        rows, setting, conditions = await asyncio.gather(
            KeyboardButtonCRUD().get_all(),
            SettingsManager().get_settings(),
            home_button_conditions(),
        )
        buttons = {row.button_key: row for row in rows}
        known = sorted(set(buttons) | set(KEYBOARD_BUTTON_TITLES) | set(KEYBOARD_BUTTON_DEFAULTS) | set(HOME_KEYS))

        entries = []
        for key in known:
            row = buttons.get(key)
            _default_style, default_icon = KEYBOARD_BUTTON_DEFAULT_STYLES.get(key, (None, None))
            entries.append(
                PanelKeyboardButton(
                    key=key,
                    section=_section_of(key),
                    title=KEYBOARD_BUTTON_TITLES.get(key, key),
                    default_text=_default_text(key),
                    text=unglass_text(row.button_text) if row and row.button_text else None,
                    style=row.button_style if row is not None else None,
                    default_icon=default_icon,
                    icon=row.button_icon if row else None,
                    hidden=bool(row is not None and getattr(row, "hidden", False)),
                    in_home=key in HOME_KEYS,
                    blocked=conditions.get(key, ""),
                )
            )

        return PanelKeyboardResponse(
            layout=_current_layout(buttons),
            buttons=entries,
            home_keys=list(HOME_KEYS),
            sections=SECTION_SLUGS,
            premium_emoji_enabled=bool(getattr(setting, "premium_emoji_status", False)) if setting else False,
            glass_mode=glass_mode_active(setting),
        )

    return await guard.run(payload, request, PanelKeyboardResponse, handle)


@router.post("/panel/keyboard/layout", response_model=ActionResponse)
async def save_layout(payload: PanelKeyboardLayoutRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        allowed = set(HOME_KEYS)
        placement: dict[str, tuple[int, int]] = {}
        row_index = 0
        for keys in payload.layout:
            row = [key for key in keys if key in allowed and key not in placement]
            if not row:
                continue
            for position, key in enumerate(row):
                placement[key] = (row_index, position)
            row_index += 1

        if not placement:
            return ActionResponse(ok=False, error="چیدمان نمی‌تواند خالی باشد.")

        hidden = {key for key in payload.hidden if key in placement}
        ok = await KeyboardButtonCRUD().set_home_layout(placement, hidden)
        await _log(
            actor,
            "keyboard_layout_update",
            target_type="keyboard",
            detail={"buttons": len(placement), "hidden": sorted(hidden)},
        )
        if not ok:
            return ActionResponse(ok=False, error="ذخیرهٔ چیدمان انجام نشد.")
        return ActionResponse(message="چیدمان ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/keyboard/layout/reset", response_model=ActionResponse)
async def reset_layout(payload: PanelRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await KeyboardButtonCRUD().reset_home_layout()
        await _log(actor, "keyboard_layout_reset", target_type="keyboard")
        if not ok:
            return ActionResponse(ok=False, error="بازگرداندن چیدمان پیش‌فرض انجام نشد.")
        return ActionResponse(message="چیدمان به حالت پیش‌فرض برگشت.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/keyboard/button", response_model=ActionResponse)
async def save_button(payload: PanelKeyboardButtonSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        key = payload.key.strip()[:100]
        if not key:
            return ActionResponse(ok=False, error="کلید دکمه الزامی است.")

        style = payload.style if payload.style in STYLE_OPTIONS else ""
        # "none" clears the built-in default colour, "" leaves it in place.
        style_value = None if style == "" else ("" if style == "none" else style)

        # The glassy look is brackets around the label, not a Telegram style, so
        # it is baked into the stored text. Handlers match a press against that
        # same stored text, which is how the button keeps working either way.
        label = unglass_text(payload.text.strip())
        setting = await SettingsManager().get_settings()
        if style == GLASS_STYLE or (glass_mode_active(setting) and key.startswith(GLASS_KEY_PREFIX)):
            label = glass_text(label)

        icon_raw = payload.icon.strip()
        try:
            icon_value = parse_icon(icon_raw)
        except ValueError:
            return ActionResponse(ok=False, error="آیدی ایموجی معتبر نیست.")

        ok = await KeyboardButtonCRUD().set_button(
            key,
            button_text=label,
            button_style=style_value,
            button_icon=icon_value,
            clear_icon=not icon_raw,
        )
        await _log(
            actor,
            "keyboard_button_update",
            target_type="keyboard_button",
            target_id=key,
            detail={"style": style_value, "icon": icon_value},
        )
        if not ok:
            return ActionResponse(ok=False, error="ذخیرهٔ دکمه انجام نشد.")
        return ActionResponse(message="دکمه ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/keyboard/icon-clear", response_model=ActionResponse)
async def clear_icon(payload: PanelKeyboardIconClearRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        key = payload.key.strip()[:100]
        if not key:
            return ActionResponse(ok=False, error="کلید دکمه الزامی است.")
        ok = await KeyboardButtonCRUD().set_button(key, clear_icon=True)
        await _log(actor, "keyboard_icon_clear", target_type="keyboard_button", target_id=key)
        if not ok:
            return ActionResponse(ok=False, error="حذف آیکون انجام نشد.")
        return ActionResponse(message="آیکون حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

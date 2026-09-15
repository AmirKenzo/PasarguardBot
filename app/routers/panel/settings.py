"""Bot settings, built from the section defaults in ``app.db.models.settings``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request

from app.db.crud.settings import SettingsManager
from app.db.models.settings import SETTINGS_SECTION_DEFAULTS
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.settings import (
    PanelSelectOption,
    PanelSettingField,
    PanelSettingSection,
    PanelSettingsResponse,
    PanelSettingsSaveRequest,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.keyboard_glass import apply_glass_mode, glass_mode_active
from app.telegram.admin.settings_payment.texts import (
    MANUAL_CARD_VISIBILITY_ALL,
    MANUAL_CARD_VISIBILITY_SAFE_MODE,
)

router = APIRouter()

# Telegram only accepts these as a message reaction; anything else is silently
# rejected, so the picker only offers ones that are actually going to work.
START_REACTION_EMOJIS: tuple[str, ...] = (
    "👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩",
    "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳", "❤🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆",
    "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
    "😇", "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪", "🗿", "🆒", "💘", "🙉", "🦄",
    "😘", "💊", "🙊", "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀", "😡",
)  # fmt: skip

# Telegram's fixed set of built-in animated message effects (id -> emoji).
# Sending any other id makes the whole message fail to send.
START_MESSAGE_EFFECTS: tuple[tuple[str, str], ...] = (
    ("5104841245755180586", "🔥"),
    ("5107584321108051014", "👍"),
    ("5104858069142078462", "👎"),
    ("5159385139981059251", "❤️"),
    ("5046509860389126442", "🎉"),
    ("5046589136895476101", "💩"),
)

# Fields whose value is a fixed set of options rather than free text or a number:
# (value, label) pairs, the value's what gets stored, the label's what the picker
# shows for it — kept together here so the two can never drift apart. The first
# option in each list is the "off" value.
SELECT_FIELD_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "manual_card_visibility": [
        (MANUAL_CARD_VISIBILITY_ALL, "همه کاربران"),
        (MANUAL_CARD_VISIBILITY_SAFE_MODE, "فقط سیف‌مود"),
    ],
    "start_reaction_emoji": [("", "خاموش"), *((emoji, emoji) for emoji in START_REACTION_EMOJIS)],
    "start_effect_id": [("0", "خاموش"), *((effect_id, emoji) for effect_id, emoji in START_MESSAGE_EFFECTS)],
}

# Select values that must be cast back to a non-string type before storage.
SELECT_FIELD_CASTERS: dict[str, Callable[[str], Any]] = {
    "start_effect_id": int,
}

# Auto-updated by a background job (app/jobs/prices.py) — never user-editable.
READONLY_FIELDS: frozenset[str] = frozenset({"arz_usd", "arz_trx", "arz_ton"})


def _current(setting: Any, section: str, key: str, default: Any) -> Any:
    if setting is None:
        return default
    data = getattr(setting, section, None)
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def _field_type(key: str, default: Any) -> str:
    if key in SELECT_FIELD_OPTIONS:
        return "select"
    if isinstance(default, bool):
        return "bool"
    return "text" if isinstance(default, str) else "number"


def _build_field(setting: Any, section: str, key: str, default: Any) -> PanelSettingField:
    value = _current(setting, section, key, default)
    options = SELECT_FIELD_OPTIONS.get(key)
    select_options = None
    if options is not None:
        # Options are always strings client-side — some (like a message effect id)
        # would lose precision as a JSON number once a browser parses them.
        text_value = "" if value is None else str(value)
        valid_values = {item_value for item_value, _ in options}
        value = text_value if text_value in valid_values else options[0][0]
        select_options = [PanelSelectOption(value=item_value, label=label) for item_value, label in options]
    return PanelSettingField(
        key=key,
        type=_field_type(key, default),
        default=default,
        value=value,
        options=select_options,
        read_only=key in READONLY_FIELDS,
    )


def _coerce(raw: Any, default: Any) -> Any:
    """Cast one submitted value to the shape the stored default implies."""
    if isinstance(default, bool):
        return bool(raw)
    if isinstance(default, str):
        # A cleared text field means "off", not "restore the default".
        return "" if raw is None else str(raw).strip()
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None if default is None else default
    number = float(str(raw).replace(",", "").strip())
    return int(number) if number.is_integer() else number


@router.post("/panel/settings", response_model=PanelSettingsResponse)
async def read_settings(payload: PanelRequest, request: Request) -> PanelSettingsResponse:
    async def handle(_: PanelActor) -> PanelSettingsResponse:
        setting = await SettingsManager().get_settings()
        return PanelSettingsResponse(
            initialized=setting is not None,
            sections=[
                PanelSettingSection(
                    key=section,
                    fields=[_build_field(setting, section, key, default) for key, default in defaults.items()],
                )
                for section, defaults in SETTINGS_SECTION_DEFAULTS.items()
            ],
        )

    return await guard.run(payload, request, PanelSettingsResponse, handle)


@router.post("/panel/settings/save", response_model=ActionResponse)
async def save_settings(payload: PanelSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        setting = await manager.get_settings()

        updates: dict[str, Any] = {}
        for defaults in SETTINGS_SECTION_DEFAULTS.values():
            for key, default in defaults.items():
                # Only touch keys the caller actually sent, so saving one section
                # of the form never resets the sections it left out.
                if key not in payload.values or key in READONLY_FIELDS:
                    continue
                if isinstance(default, bool):
                    updates[key] = bool(payload.values[key])
                    continue
                if key in SELECT_FIELD_OPTIONS:
                    raw = payload.values[key]
                    if raw not in {item_value for item_value, _ in SELECT_FIELD_OPTIONS[key]}:
                        return ActionResponse(ok=False, error=f"مقدار «{key}» نامعتبر است.")
                    caster = SELECT_FIELD_CASTERS.get(key)
                    updates[key] = caster(raw) if caster else raw
                    continue
                try:
                    updates[key] = _coerce(payload.values[key], default)
                except ValueError:
                    return ActionResponse(ok=False, error=f"مقدار «{key}» عددی نیست.")

        glass_before = glass_mode_active(setting)
        if setting is None:
            await manager.add_setting(**updates)
        else:
            await manager.update_setting(setting.id, **updates)

        # The glassy look is baked into the stored button labels, so flipping the
        # switch has to rewrite them; nothing else here has work to do after the save.
        glass_after = bool(updates.get("glass_buttons_mode", glass_before))
        if glass_after != glass_before:
            await apply_glass_mode(glass_after)

        await audit.record(
            admin_id=actor.user_id,
            admin_username=actor.username,
            action="settings_update",
            target_type="settings",
            detail={"keys": sorted(updates)},
            ip=actor.ip,
        )
        return ActionResponse(message="تنظیمات ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)

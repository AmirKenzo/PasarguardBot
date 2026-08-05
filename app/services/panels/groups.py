"""Panel default-group selection helpers (add/change panel wizard)."""

from __future__ import annotations

import json
from collections.abc import Callable
from random import randint

from telethon import Button

from app.db.crud.panels import PanelsManager
from app.services.panels.auth import (
    AUTH_API_KEY,
    PANEL_AUTH_PLACEHOLDER_USERNAME,
    PanelGroupsResponse,
    fetch_panel_groups_with_auth,
    verify_panel_api_key,
    verify_panel_password,
)
from app.services.panels.settings import panel_default_group_ids
from app.telegram.state import set_step
from app.telegram.state.store import clear_user_conversation, get_user_state
from app.utils.security.crypto import encrypt_data

panel_group_cache: dict[tuple[str, int, int | None], list[tuple[int, str]]] = {}


def serialize_group_ids(group_ids: list[int] | None) -> str | None:
    if not group_ids:
        return None
    unique_sorted = sorted({int(g) for g in group_ids})
    return json.dumps(unique_sorted, ensure_ascii=False)


def deserialize_group_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data]
    except TypeError, ValueError, json.JSONDecodeError:
        pass
    try:
        return [int(x) for x in str(raw).split(",") if x.strip().isdigit()]
    except Exception:
        return []


def step_data_to_group_ids(data: str | int | list | None) -> list[int]:
    if data is None:
        return []
    if isinstance(data, int):
        return [data]
    if isinstance(data, list):
        return [int(x) for x in data]
    raw = str(data).strip()
    if not raw:
        return []
    if raw.isdigit():
        return [int(raw)]
    if raw.startswith("["):
        return deserialize_group_ids(raw)
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def group_ids_to_step_data(group_ids: list[int]) -> str:
    return ",".join(str(i) for i in sorted({int(g) for g in group_ids}))


def resolve_panel_group_ids(panel, groups_resp: PanelGroupsResponse) -> list[int]:
    selected_ids = sorted(
        {gid for gid in panel_default_group_ids(panel) if any(g.id == gid for g in groups_resp.groups)}
    )
    if selected_ids:
        return selected_ids
    return [g.id for g in groups_resp.groups]


def get_panel_default_group_name(panel, groups_resp: PanelGroupsResponse) -> str:
    groups_map = {g.id: g.name for g in groups_resp.groups}
    selected_ids = panel_default_group_ids(panel)
    if not groups_resp.groups:
        return "هیچ گروهی یافت نشد"
    if not selected_ids:
        return "تمام گروه‌ها"
    selected_names = [groups_map.get(gid) for gid in selected_ids if gid in groups_map]
    selected_names = [name for name in selected_names if name]
    if not selected_names:
        return "گروه یافت نشد"
    if len(selected_names) <= 3:
        return "، ".join(selected_names)
    return f"{len(selected_names)} گروه انتخاب‌شده"


async def fetch_panel_groups(panel) -> PanelGroupsResponse:
    return await fetch_panel_groups_with_auth(panel)


async def create_panel_with_group(user_id: int, default_group_ids: list[int] | None):
    panel_name = await get_user_state(user_id, "name")
    panel_url = await get_user_state(user_id, "url")
    auth_type = await get_user_state(user_id, "auth_type") or "password"

    if auth_type == AUTH_API_KEY:
        api_key = (await get_user_state(user_id, "api_key") or "").strip()
        if not all([panel_name, panel_url, api_key]):
            raise ValueError("اطلاعات پنل کامل نیست.")
        panel_url = panel_url.strip()
        _authed, groups_resp = await verify_panel_api_key(panel_url, api_key)
        stored_password = ""
        cookie = api_key
        panel_username = PANEL_AUTH_PLACEHOLDER_USERNAME
    else:
        panel_username = await get_user_state(user_id, "username")
        panel_password = await get_user_state(user_id, "password")
        if not all([panel_name, panel_url, panel_username, panel_password]):
            raise ValueError("اطلاعات پنل کامل نیست.")
        panel_url = panel_url.strip()
        panel_username = panel_username.strip()
        panel_password = panel_password.strip()
        _authed, jwt_token, groups_resp = await verify_panel_password(panel_url, panel_username, panel_password)
        stored_password = encrypt_data(panel_password)
        cookie = jwt_token

    if default_group_ids:
        group_ids_set = {g.id for g in groups_resp.groups}
        missing = [gid for gid in default_group_ids if gid not in group_ids_set]
        if missing:
            raise ValueError("برخی گروه‌های انتخاب‌شده در این پنل وجود ندارند.")

    panel_manager = PanelsManager()
    for _ in range(5):
        panel_code = randint(10000, 99999)
        existing = await panel_manager.get_panel_by_code(panel_code)
        if not existing:
            break
    else:
        raise ValueError("امکان ایجاد کد یکتا برای پنل وجود ندارد.")

    storage_value = serialize_group_ids(default_group_ids)

    new_panel = await panel_manager.add_panel(
        code=panel_code,
        name=panel_name,
        enable=1,
        base_url=panel_url,
        username=panel_username,
        password=stored_password,
        cookie=cookie,
        default_group_ids=storage_value,
        auth_type=auth_type,
    )

    await clear_user_conversation(user_id)
    await set_step(user_id, "Menu_panels")

    return new_panel, storage_value


def make_group_cache_key(context: str, user_id: int, panel_code: int | None = None) -> tuple[str, int, int | None]:
    return (context, user_id, panel_code)


def cache_panel_groups(
    context: str, user_id: int, groups: list[tuple[int, str]], panel_code: int | None = None
) -> None:
    panel_group_cache[make_group_cache_key(context, user_id, panel_code)] = groups


def get_cached_panel_groups(context: str, user_id: int, panel_code: int | None = None) -> list[tuple[int, str]]:
    return panel_group_cache.get(make_group_cache_key(context, user_id, panel_code), [])


async def get_add_panel_groups_from_redis(user_id: int) -> list[tuple[int, str]]:
    """Get add-panel groups list from Redis (set when showing group selection)."""
    data = await get_user_state(user_id, "panel_add_groups_list")
    if not data:
        return []
    # store.py already JSON-deserializes values; keep backward compatibility
    # for old sessions that may still have raw JSON string payloads.
    raw = data
    if isinstance(data, str):
        try:
            raw = json.loads(data)
        except TypeError, ValueError, json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    parsed: list[tuple[int, str]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            parsed.append((int(item[0]), str(item[1])))
        except TypeError, ValueError:
            continue
    return parsed


def clear_cached_panel_groups(context: str, user_id: int, panel_code: int | None = None) -> None:
    panel_group_cache.pop(make_group_cache_key(context, user_id, panel_code), None)


def build_group_list_text(groups: list[tuple[int, str]]) -> str:
    if not groups:
        return "هیچ گروهی برای این پنل تعریف نشده است."
    return "\n".join(f"- {name} (ID: {gid})" for gid, name in groups)


def summarize_selected_groups(groups: list[tuple[int, str]], selected_ids: list[int]) -> str:
    if not groups:
        return "هیچ گروهی برای این پنل تعریف نشده است."
    if not selected_ids or len(selected_ids) >= len(groups):
        return "تمام گروه‌ها"
    names = [name for gid, name in groups if gid in selected_ids]
    if names:
        return "، ".join(names)
    return "هیچ گروهی انتخاب نشده است"


def build_add_panel_group_message(groups: list[tuple[int, str]], selected_ids: list[int]) -> str:
    groups_text = build_group_list_text(groups)
    summary = summarize_selected_groups(groups, selected_ids)
    return (
        "✅ اتصال به پنل موفق بود.\n"
        "📋 لیست گروه‌های این پنل:\n"
        f"{groups_text}\n\n"
        f"گروه‌های انتخاب‌شده: {summary}\n\n"
        "با استفاده از دکمه‌ها گروه‌ها را اضافه یا حذف کن و در پایان «تایید» را بزن."
    )


def build_change_panel_group_message(groups: list[tuple[int, str]], selected_ids: list[int]) -> str:
    groups_text = build_group_list_text(groups)
    summary = summarize_selected_groups(groups, selected_ids)
    return (
        "📋 لیست گروه‌های این پنل:\n"
        f"{groups_text}\n\n"
        f"گروه‌های انتخاب‌شده: {summary}\n\n"
        "برای تغییر انتخاب روی دکمه‌ها کلیک کن و در پایان «تایید» را بزن."
    )


def build_group_selection_buttons(
    groups: list[tuple[int, str]],
    selected_ids: list[int],
    toggle_data_fn: Callable[[int], str],
    confirm_data: str,
    cancel_data: str,
    select_all_data: str | None,
) -> list[list[Button]]:
    buttons: list[list[Button]] = []
    row: list[Button] = []
    for gid, name in groups:
        label = f"✅ {name}" if gid in selected_ids else name
        row.append(Button.inline(label, data=toggle_data_fn(gid)))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if select_all_data:
        buttons.append([Button.inline("استفاده از همه گروه‌ها", data=select_all_data)])
    buttons.append(
        [
            Button.inline("✅ تایید", data=confirm_data),
            Button.inline("❌ انصراف", data=cancel_data),
        ]
    )
    return buttons

"""Callback handlers for admin help management."""

from __future__ import annotations

import contextlib
import json

from telethon import events
from telethon.errors import MessageNotModifiedError

from app.db.crud.help_buttons import HelpDownloadAppCRUD
from app.telegram.admin.help import keyboards, states, texts
from app.telegram.shared.utils.help_download import (
    LEGACY_APPS as default_apps,
    create_download_app_config_submenu,
    delete_target,
    fetch_app,
    load_targets,
    migrate_categories_to_targets,
    patterns_edit_hint,
    target_by_id,
    targets_list_buttons,
    targets_list_message,
    update_target,
)
from app.telegram.state import delete_data, get_data, set_data, set_step
from config import ADMIN_ID


async def _safe_edit_target_screen(event: events.CallbackQuery.Event, app_id: int, target: dict) -> None:
    text, buttons = keyboards.target_edit_screen(app_id, target)
    with contextlib.suppress(MessageNotModifiedError):
        await event.edit(text, buttons=buttons)


async def help_download_apps_admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    if data == "help_download_apps_manage":
        if event.sender_id not in ADMIN_ID:
            await event.answer(texts.ACCESS_DENIED_TEXT, alert=True)
            return
        crud = HelpDownloadAppCRUD()
        apps_list = await crud.get_all()
        await event.edit(
            texts.APPS_LIST_TEXT,
            buttons=keyboards.apps_manage_rows(apps_list),
        )
        return

    if data.startswith("help_download_app_config:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        app = await crud.get_by_id(app_id)
        if not app:
            await event.answer(texts.APP_NOT_FOUND_TEXT, alert=True)
            return
        submenu = create_download_app_config_submenu(app_id, app)
        await event.edit(
            texts.app_config_text(app.button_text),
            buttons=submenu,
        )
        return

    if data.startswith("help_download_app_config_color:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        parts = data.split(":")
        if len(parts) < 3:
            return
        app_id = int(parts[1])
        style_val = parts[2]
        crud = HelpDownloadAppCRUD()
        app = await crud.get_by_id(app_id)
        if not app:
            await event.answer(texts.APP_NOT_FOUND_TEXT, alert=True)
            return
        if style_val == "none":
            await crud.update(app_id, button_style="")
            await event.answer(texts.BUTTON_STYLE_CLEARED_TEXT)
        else:
            await crud.update(app_id, button_style=style_val)
            await event.answer(texts.button_style_changed_text(style_val))
        app = await crud.get_by_id(app_id)
        submenu = create_download_app_config_submenu(app_id, app)
        try:
            await event.edit(texts.app_config_text(app.button_text), buttons=submenu)
        except MessageNotModifiedError:
            await event.answer()
        return

    if data.startswith("help_download_app_config_icon:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_SET_ICON)
        await event.edit(
            texts.SET_ICON_PROMPT_TEXT,
            buttons=[keyboards.back_to_config_row(app_id)],
        )
        return

    if data.startswith("help_download_app_config_icon_clear:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        crud = HelpDownloadAppCRUD()
        await crud.update(app_id, clear_icon=True)
        app = await crud.get_by_id(app_id)
        submenu = create_download_app_config_submenu(app_id, app)
        await event.answer(texts.ICON_CLEARED_TEXT)
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(
                texts.app_config_text(app.button_text if app else ""),
                buttons=submenu,
            )
        return

    if data.startswith("help_download_app_config_edit_text:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_EDIT_TEXT)
        await event.edit(
            texts.EDIT_BUTTON_TEXT_PROMPT,
            buttons=[keyboards.back_to_config_row(app_id)],
        )
        return

    if data.startswith("help_download_app_config_repo:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_REPO)
        await event.edit(
            texts.EDIT_REPO_PROMPT,
            buttons=[keyboards.back_to_config_row(app_id)],
        )
        return

    if data.startswith("help_download_app_config_ios:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_IOS)
        await event.edit(
            texts.EDIT_IOS_PROMPT,
            buttons=[keyboards.back_to_config_row(app_id)],
        )
        return

    if data.startswith("help_download_app_config_custom_msg:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_CUSTOM_MSG)
        await event.edit(
            texts.EDIT_CUSTOM_MSG_PROMPT,
            buttons=[keyboards.back_to_config_row(app_id)],
        )
        return

    if data == "help_download_app_add_text":
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_TEXT1)
        await event.edit(
            texts.ADD_TEXT_ONLY_STEP1_TEXT,
            buttons=[keyboards.cancel_row()],
        )
        return

    if data == "help_download_app_add_defaults":
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        crud = HelpDownloadAppCRUD()
        added = 0
        for key, app in default_apps.items():
            ck = (key or "").strip().lower().replace(" ", "_")
            if await crud.get_by_callback_key(ck):
                continue
            ok = await crud.create(
                button_text=app.get("display_name", key),
                callback_key=ck,
                repo_owner=app["repo_owner"],
                repo_name=app["repo_name"],
                categories=app.get("categories", {}),
                default_file=app.get("default_file"),
            )
            if ok:
                added += 1
        apps_list = await crud.get_all()
        await event.edit(
            texts.defaults_added_text(added),
            buttons=keyboards.apps_manage_rows(apps_list),
        )
        return

    if data.startswith("help_download_app_cat:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        preset = data.split(":")[1] if ":" in data else "default"
        categories = states.DEFAULT_CATEGORIES if preset == "default" else states.ANDROID_ONLY_CATEGORIES
        await set_data(
            event.sender_id,
            states.HELP_DOWNLOAD_APP_ADD_CATEGORIES,
            json.dumps(categories),
        )
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD4)
        await event.edit(
            texts.ADD_GITHUB_STEP4_TEXT,
            buttons=keyboards.ios_skip_rows(),
        )
        return

    if data == "help_download_app_ios_skip":
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        button_text = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_BUTTON_TEXT)
        owner = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_OWNER)
        name = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_NAME)
        cat_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_CATEGORIES)
        categories = cat_str if isinstance(cat_str, dict) else json.loads(cat_str) if cat_str else {}
        for key in states.IOS_SKIP_STEP_KEYS:
            await delete_data(event.sender_id, key)
        await set_step(event.sender_id, "home")
        callback_key = (button_text or "").lower().replace(" ", "_").replace(".", "_")[:80]
        crud = HelpDownloadAppCRUD()
        existing = await crud.get_by_callback_key(callback_key)
        if existing:
            callback_key = f"{callback_key}_{existing.id}"
        app = await crud.create(
            button_text=button_text or "",
            callback_key=callback_key,
            repo_owner=owner or "",
            repo_name=name or "",
            categories=categories,
            ios_url=None,
        )
        if app:
            apps_list = await crud.get_all()
            await event.edit(
                texts.app_added_text(app.button_text),
                buttons=keyboards.apps_manage_rows(apps_list),
            )
        else:
            await event.answer(texts.SAVE_ERROR_TEXT, alert=True)
        return

    if data == "help_download_app_add":
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD1)
        await event.edit(
            texts.ADD_GITHUB_APP_STEP1_TEXT,
            buttons=[keyboards.cancel_row()],
        )
        return

    if data == "help_download_app_cancel":
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        for key in states.CANCEL_STEP_KEYS:
            await delete_data(event.sender_id, key)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        apps_list = await crud.get_all()
        await event.edit(
            texts.APPS_MANAGE_CANCELLED_TEXT,
            buttons=keyboards.apps_manage_rows(apps_list),
        )
        return

    if data.startswith("help_download_app_targets:"):
        app_id = int(data.split(":")[1])
        app = await fetch_app(app_id)
        if not app:
            await event.answer(texts.APP_NOT_FOUND_TEXT, alert=True)
            return
        targets = await load_targets(app_id)
        await event.edit(
            targets_list_message(app, targets),
            buttons=targets_list_buttons(app_id, targets),
        )
        return

    if data.startswith("help_download_app_target_migrate:"):
        app_id = int(data.split(":")[1])
        ok = await migrate_categories_to_targets(app_id)
        app = await fetch_app(app_id)
        targets = await load_targets(app_id)
        await event.answer(texts.MIGRATE_OK_TEXT if ok else texts.MIGRATE_SKIP_TEXT)
        if app:
            await event.edit(
                targets_list_message(app, targets),
                buttons=targets_list_buttons(app_id, targets),
            )
        return

    if data.startswith("help_download_app_target_add:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        await set_data(event.sender_id, states.HELP_DL_TGT_APP_ID, str(app_id))
        await set_step(event.sender_id, states.HELP_DL_TGT_ADD_TEXT)
        await event.edit(
            texts.ADD_TARGET_TEXT_PROMPT,
            buttons=[keyboards.back_to_targets_row(app_id)],
        )
        return

    if data.startswith("help_download_app_target:"):
        parts = data.split(":")
        if len(parts) < 3:
            return
        app_id = int(parts[1])
        target_id = parts[2]
        app = await fetch_app(app_id)
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if not app or not target:
            await event.answer(texts.NOT_FOUND_TEXT, alert=True)
            return
        await _safe_edit_target_screen(event, app_id, target)
        return

    if data.startswith("help_download_app_target_del:"):
        parts = data.split(":")
        app_id = int(parts[1])
        target_id = parts[2]
        await delete_target(app_id, target_id)
        app = await fetch_app(app_id)
        targets = await load_targets(app_id)
        await event.answer(texts.TARGET_DELETED_TEXT)
        if app:
            await event.edit(
                targets_list_message(app, targets),
                buttons=targets_list_buttons(app_id, targets),
            )
        return

    if data.startswith("help_download_app_target_text:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        parts = data.split(":")
        app_id, target_id = int(parts[1]), parts[2]
        await set_data(event.sender_id, states.HELP_DL_TGT_APP_ID, str(app_id))
        await set_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID, target_id)
        await set_step(event.sender_id, states.HELP_DL_TGT_EDIT_TEXT)
        await event.edit(
            texts.EDIT_BUTTON_TEXT_PROMPT,
            buttons=[keyboards.back_to_target_row(app_id, target_id)],
        )
        return

    if data.startswith("help_download_app_target_patterns:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        parts = data.split(":")
        app_id, target_id = int(parts[1]), parts[2]
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if not target:
            await event.answer(texts.NOT_FOUND_TEXT, alert=True)
            return
        await set_data(event.sender_id, states.HELP_DL_TGT_APP_ID, str(app_id))
        await set_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID, target_id)
        await set_step(event.sender_id, states.HELP_DL_TGT_EDIT_PATTERNS)
        await event.edit(
            patterns_edit_hint(target),
            buttons=[keyboards.back_to_target_row(app_id, target_id)],
        )
        return

    if data.startswith("help_download_app_target_color:"):
        parts = data.split(":")
        app_id, target_id, style_val = int(parts[1]), parts[2], parts[3]
        style = "" if style_val == "none" else style_val
        await update_target(app_id, target_id, button_style=style)
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if not target:
            await event.answer(texts.NOT_FOUND_TEXT, alert=True)
            return
        await event.answer(texts.target_color_changed_text(style_val), alert=True)
        await _safe_edit_target_screen(event, app_id, target)
        return

    if data.startswith("help_download_app_target_icon:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        parts = data.split(":")
        app_id, target_id = int(parts[1]), parts[2]
        await set_data(event.sender_id, states.HELP_DL_TGT_APP_ID, str(app_id))
        await set_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID, target_id)
        await set_step(event.sender_id, states.HELP_DL_TGT_SET_ICON)
        await event.edit(
            texts.SET_TARGET_ICON_PROMPT,
            buttons=[keyboards.back_to_target_row(app_id, target_id)],
        )
        return

    if data.startswith("help_download_app_target_icon_clear:"):
        parts = data.split(":")
        app_id, target_id = int(parts[1]), parts[2]
        await update_target(app_id, target_id, button_icon=None)
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        await event.answer(texts.TARGET_ICON_CLEARED_TEXT, alert=True)
        if target:
            await _safe_edit_target_screen(event, app_id, target)
        return

    if data.startswith("help_download_app_del:"):
        if event.sender_id not in ADMIN_ID:
            await event.answer()
            return
        app_id = int(data.split(":")[1])
        ok = await HelpDownloadAppCRUD().delete(app_id)
        if ok:
            await event.answer(texts.APP_DELETED_TEXT, alert=True)
            crud = HelpDownloadAppCRUD()
            apps_list = await crud.get_all()
            await event.edit(
                texts.APPS_MANAGE_TITLE,
                buttons=keyboards.apps_manage_rows(apps_list),
            )
        else:
            await event.answer(texts.DELETE_ERROR_TEXT, alert=True)
        return

    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        help_download_apps_admin_callback,
        events.CallbackQuery(
            pattern=rb"^help_download_app",
            func=lambda e: e.sender_id in ADMIN_ID,
        ),
    )

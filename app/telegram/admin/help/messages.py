"""Message handlers for admin help management."""

from __future__ import annotations

import json

from telethon import events
from telethon.tl.custom import Message

from app.db.crud.help_buttons import HelpDownloadAppCRUD
from app.telegram.admin.help import keyboards, states, texts
from app.telegram.keyboards.common import extract_custom_emoji_document_id
from app.telegram.shared.utils.help_download import (
    append_target,
    create_download_app_config_submenu,
    fetch_app,
    load_targets,
    run_admin_app_files_sync,
    target_by_id,
    targets_list_buttons,
    targets_list_message,
    update_target,
)
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID


async def _help_download_admin_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    msg = (event.message.text or "").strip()
    if msg == texts.UPDATE_APPS_MESSAGE:
        return True
    return (await get_step(event.sender_id)) in states.HELP_DOWNLOAD_ADMIN_STEPS


async def help_download_admin_message(event: Message):
    msg = event.message.text or ""
    step = await get_step(event.sender_id)

    if msg == texts.UPDATE_APPS_MESSAGE:
        status_message = await event.reply(texts.UPDATE_APPS_STATUS_TEXT)
        await run_admin_app_files_sync(status_message)
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_CONFIG_SET_ICON and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        if msg.strip().lower() == "/skip":
            await crud.update(app_id, clear_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(texts.INVALID_PREMIUM_EMOJI_TEXT)
                raise events.StopPropagation
            await crud.update(app_id, button_icon=icon_id)
        app = await crud.get_by_id(app_id)
        submenu = create_download_app_config_submenu(app_id, app)
        await event.respond(
            texts.icon_set_with_config_text(app.button_text if app else ""),
            buttons=submenu,
        )
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_CONFIG_EDIT_TEXT and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        await crud.update(app_id, button_text=msg.strip())
        app = await crud.get_by_id(app_id)
        await event.respond(texts.BUTTON_TEXT_UPDATED_TEXT, buttons=create_download_app_config_submenu(app_id, app))
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_CONFIG_REPO and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        repo = msg.strip()
        if "/" not in repo or repo.count("/") != 1:
            await event.respond(texts.INVALID_REPO_FORMAT_TEXT)
            raise events.StopPropagation
        owner, name = repo.split("/", 1)
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        await crud.update(app_id, repo_owner=owner.strip(), repo_name=name.strip())
        app = await crud.get_by_id(app_id)
        await event.respond(texts.REPO_UPDATED_TEXT, buttons=create_download_app_config_submenu(app_id, app))
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_CONFIG_IOS and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        ios_url = msg.strip() if msg.strip() and msg.strip() != "-" else None
        if ios_url and not ios_url.startswith(("http://", "https://")):
            ios_url = "https://" + ios_url
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        await crud.update(app_id, ios_url=ios_url)
        app = await crud.get_by_id(app_id)
        await event.respond(texts.IOS_UPDATED_TEXT, buttons=create_download_app_config_submenu(app_id, app))
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_CONFIG_CUSTOM_MSG and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_CONFIG_APP_ID)
        await set_step(event.sender_id, "home")
        crud = HelpDownloadAppCRUD()
        await crud.update(app_id, custom_message=msg.strip())
        app = await crud.get_by_id(app_id)
        await event.respond(texts.CUSTOM_MSG_UPDATED_TEXT, buttons=create_download_app_config_submenu(app_id, app))
        raise events.StopPropagation

    if step == states.HELP_DL_TGT_ADD_TEXT and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        await set_data(event.sender_id, states.HELP_DL_TGT_ADD_BUTTON_TEXT, msg.strip())
        await set_step(event.sender_id, states.HELP_DL_TGT_ADD_PATTERNS)
        await event.respond(
            texts.ADD_TARGET_PATTERNS_TEXT,
            buttons=[keyboards.back_to_targets_row(int(app_id_str))],
        )
        raise events.StopPropagation

    if step == states.HELP_DL_TGT_ADD_PATTERNS and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        button_text = await get_data(event.sender_id, states.HELP_DL_TGT_ADD_BUTTON_TEXT)
        if not app_id_str:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        patterns = [ln.strip() for ln in msg.strip().splitlines() if ln.strip()]
        if not patterns:
            await event.respond(texts.MIN_PATTERN_REQUIRED_TEXT)
            raise events.StopPropagation
        await delete_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        await delete_data(event.sender_id, states.HELP_DL_TGT_ADD_BUTTON_TEXT)
        await set_step(event.sender_id, "home")
        await append_target(app_id, button_text or "دانلود", patterns)
        app = await fetch_app(app_id)
        targets = await load_targets(app_id)
        await event.respond(
            texts.TARGET_ADDED_TEXT,
            buttons=targets_list_buttons(app_id, targets) if app else None,
        )
        if app:
            await event.respond(targets_list_message(app, targets))
        raise events.StopPropagation

    if step == states.HELP_DL_TGT_EDIT_TEXT and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        target_id = await get_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        if not app_id_str or not target_id:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        await delete_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        await delete_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        await set_step(event.sender_id, "home")
        await update_target(app_id, target_id, button_text=msg.strip())
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if target:
            text, buttons = keyboards.target_edit_screen(app_id, target)
            await event.respond(text, buttons=buttons)
        raise events.StopPropagation

    if step == states.HELP_DL_TGT_EDIT_PATTERNS and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        target_id = await get_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        if not app_id_str or not target_id:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        app_id = int(app_id_str)
        patterns = [ln.strip() for ln in msg.strip().splitlines() if ln.strip()]
        if not patterns:
            await event.respond(texts.MIN_PATTERN_REQUIRED_TEXT)
            raise events.StopPropagation
        await delete_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        await delete_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        await set_step(event.sender_id, "home")
        await update_target(app_id, target_id, patterns=patterns)
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if target:
            text, buttons = keyboards.target_edit_screen(app_id, target)
            await event.respond(text, buttons=buttons)
        raise events.StopPropagation

    if step == states.HELP_DL_TGT_SET_ICON and msg:
        app_id_str = await get_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        target_id = await get_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        if not app_id_str or not target_id:
            await set_step(event.sender_id, "home")
            raise events.StopPropagation
        icon_id = extract_custom_emoji_document_id(event.message)
        if icon_id is None:
            await event.respond(texts.INVALID_ICON_TEXT)
            raise events.StopPropagation
        app_id = int(app_id_str)
        await delete_data(event.sender_id, states.HELP_DL_TGT_APP_ID)
        await delete_data(event.sender_id, states.HELP_DL_TGT_TARGET_ID)
        await set_step(event.sender_id, "home")
        await update_target(app_id, target_id, button_icon=icon_id)
        targets = await load_targets(app_id)
        target = target_by_id(targets, target_id)
        if target:
            text, buttons = keyboards.target_edit_screen(app_id, target)
            await event.respond(text, buttons=buttons)
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_ADD_TEXT1 and msg:
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_TEXT_BUTTON_TEXT, msg.strip())
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_TEXT2)
        await event.respond(
            texts.ADD_TEXT_ONLY_STEP2_TEXT,
            buttons=[keyboards.cancel_row()],
        )
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_ADD_TEXT2 and msg:
        button_text = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_TEXT_BUTTON_TEXT)
        await delete_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_TEXT_BUTTON_TEXT)
        await set_step(event.sender_id, "home")
        callback_key = (button_text or "").lower().replace(" ", "_").replace(".", "_")[:80]
        crud = HelpDownloadAppCRUD()
        existing = await crud.get_by_callback_key(callback_key)
        if existing:
            callback_key = f"{callback_key}_{existing.id}"
        app = await crud.create_text_only(
            button_text=button_text or "", callback_key=callback_key, custom_message=msg.strip()
        )
        if app:
            await event.respond(
                texts.text_only_added_text(app.button_text),
                buttons=[keyboards.back_to_apps_manage_row()],
            )
        else:
            await event.respond(texts.DUPLICATE_KEY_ERROR_TEXT)
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_ADD1 and msg:
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_BUTTON_TEXT, msg.strip())
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD2)
        await event.respond(texts.ADD_GITHUB_STEP2_TEXT)
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_ADD2 and msg:
        repo = msg.strip()
        if "/" not in repo or repo.count("/") != 1:
            await event.respond(texts.INVALID_REPO_FORMAT_EXAMPLE_TEXT)
            raise events.StopPropagation
        owner, name = repo.split("/", 1)
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_OWNER, owner.strip())
        await set_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_NAME, name.strip())
        await set_step(event.sender_id, states.HELP_DOWNLOAD_APP_ADD3)
        await event.respond(
            texts.ADD_GITHUB_STEP3_TEXT,
            buttons=keyboards.category_selection_rows(),
        )
        raise events.StopPropagation

    if step == states.HELP_DOWNLOAD_APP_ADD4 and msg:
        button_text = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_BUTTON_TEXT)
        owner = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_OWNER)
        name = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_REPO_NAME)
        cat_str = await get_data(event.sender_id, states.HELP_DOWNLOAD_APP_ADD_CATEGORIES)
        categories = cat_str if isinstance(cat_str, dict) else json.loads(cat_str) if cat_str else {}
        ios_url = msg.strip() if msg.strip() and msg.strip() != "-" else None
        if ios_url and not ios_url.startswith(("http://", "https://")):
            ios_url = "https://" + ios_url
        callback_key = button_text.lower().replace(" ", "_").replace(".", "_")[:80]
        crud = HelpDownloadAppCRUD()
        existing = await crud.get_by_callback_key(callback_key)
        if existing:
            callback_key = f"{callback_key}_{existing.id}"
        app = await crud.create(
            button_text=button_text,
            callback_key=callback_key,
            repo_owner=owner,
            repo_name=name,
            categories=categories,
            ios_url=ios_url,
        )
        for key in states.ADD_FLOW_STEP_KEYS:
            await delete_data(event.sender_id, key)
        await set_step(event.sender_id, "home")
        if app:
            await event.respond(
                texts.github_app_added_text(app.button_text, app.callback_key),
                buttons=[keyboards.back_to_apps_manage_row()],
            )
        else:
            await event.respond(texts.DUPLICATE_KEY_ERROR_TEXT)
        raise events.StopPropagation


def register(client):
    client.add_event_handler(
        help_download_admin_message,
        events.NewMessage(incoming=True, func=_help_download_admin_message_filter),
    )

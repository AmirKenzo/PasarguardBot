from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from telethon import utils
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import (
    Channel,
    ChannelParticipant,
    ChannelParticipantAdmin,
    ChannelParticipantCreator,
)

from app.logger import get_logger
from app.telegram.shared.utils.api import sleep_flood_wait
from config import BOT_TOKEN

logger = get_logger(__name__)


async def check_user_in_channel(client, user_id, channel, semaphore):
    """Check one channel membership for a user."""
    async with semaphore:
        try:
            participant = await client(GetParticipantRequest(channel=channel["id"], participant=user_id))

            if isinstance(
                participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator, ChannelParticipant)
            ):
                return None
        except UserNotParticipantError:
            return channel
        except FloodWaitError as e:
            logger.warning("محدودیت فلود - انتظار %s ثانیه", e.seconds)
            await sleep_flood_wait(e)
            return await check_user_in_channel(client, user_id, channel, semaphore)
        except Exception as e:
            logger.error("خطا در بررسی کانال %s: %s", channel["id"], e)
            return channel
    return None


async def check_user_channels(user_id, client, channels, max_concurrent_requests=5):
    """Check a list of lock channels and return channels the user is not a member of."""
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    tasks = [check_user_in_channel(client, user_id, channel, semaphore) for channel in channels]
    results = await asyncio.gather(*tasks)
    return [channel for channel in results if channel is not None]


def parse_telegram_message_link(link: str) -> tuple[int, int] | None:
    """Parse https://t.me/c/CHAT_ID/TOPIC_ID/MESSAGE_ID into (chat_id, topic_id)."""
    try:
        link = link.strip()
        pattern = r"https?://t\.me/c/(\d+)/(\d+)/(\d+)"
        match = re.match(pattern, link)
        if match:
            chat_id_str = match.group(1)
            topic_id = int(match.group(2))
            chat_id = int(f"-100{chat_id_str}")
            return chat_id, topic_id
        return None
    except Exception:
        return None


def _extract_invite_hash(raw: str) -> str | None:
    raw = (raw or "").strip()
    match = re.search(r"(?:https?://)?t\.me/(?:joinchat/|\+)([A-Za-z0-9_-]+)", raw)
    return match.group(1) if match else None


def _extract_tme_c_chat_id(raw: str) -> int | None:
    raw = (raw or "").strip()
    match = re.search(r"(?:https?://)?t\.me/c/(\d+)", raw)
    if not match:
        return None
    return int(f"-100{match.group(1)}")


def extract_tme_c_chat_id(raw: str) -> int | None:
    """Extract -100... chat_id from a t.me/c/... link."""
    return _extract_tme_c_chat_id(raw)


async def check_bot_channel_access(client, channel_id: int) -> tuple[bool, str | None]:
    """Check whether the bot has access to a channel/supergroup."""
    try:
        bot_me = await client.get_me()
        participant = await client(GetParticipantRequest(channel=channel_id, participant=bot_me.id))

        if isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
            return True, None
        if isinstance(participant.participant, ChannelParticipant):
            return True, "warning_not_admin"
        return False, "not_member"
    except UserNotParticipantError:
        return False, "not_member"
    except Exception as e:
        logger.error("Error checking bot access to channel %s: %s", channel_id, e)
        return False, f"error: {type(e).__name__}"


async def resolve_lock_channel_from_input(client, raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a lock-channel input into database-friendly id/title/link fields."""
    raw = (raw or "").strip()
    if not raw or len(raw) < 3:
        return None, "empty_input"

    entity = None
    errors: list[str] = []

    try:
        cleaned = raw.strip().lstrip("-")
        if cleaned.isdigit():
            channel_id = int(raw.strip())
            if channel_id < 0:
                try:
                    entity = await client.get_entity(channel_id)
                    if isinstance(entity, Channel):
                        peer_id = utils.get_peer_id(entity)
                        title = (getattr(entity, "title", None) or "").strip() or f"کانال {channel_id}"
                        username = getattr(entity, "username", None)
                        if username:
                            link = f"https://t.me/{username}"
                        else:
                            invite_link, _invite_error = await botapi_create_invite_link(channel_id)
                            if invite_link:
                                link = invite_link
                            else:
                                c_id = abs(channel_id) - 1000000000000
                                link = f"https://t.me/c/{c_id}"
                        return {"id": int(peer_id), "title": title, "link": link}, None
                except Exception:
                    invite_link, _invite_error = await botapi_create_invite_link(channel_id)
                    if invite_link:
                        return {
                            "id": int(channel_id),
                            "title": f"کانال {channel_id}",
                            "link": invite_link,
                        }, "id_parsed_with_botapi_link"
                    c_id = abs(channel_id) - 1000000000000
                    return {
                        "id": int(channel_id),
                        "title": f"کانال {channel_id}",
                        "link": f"https://t.me/c/{c_id}",
                    }, "id_parsed_no_entity"
    except (ValueError, TypeError):
        pass

    if raw.startswith("@"):
        raw = f"https://t.me/{raw[1:]}"

    try:
        entity = await client.get_entity(raw)
    except Exception as e:
        entity = None
        errors.append(f"get_entity failed: {type(e).__name__}: {str(e)[:180]}")

    if entity is None:
        invite_hash = _extract_invite_hash(raw)
        if invite_hash:
            try:
                async for dialog in client.iter_dialogs():
                    if isinstance(dialog.entity, Channel):
                        try:
                            channel_entity = dialog.entity
                            peer_id = utils.get_peer_id(channel_entity)
                            title = (getattr(channel_entity, "title", None) or "").strip() or f"کانال {peer_id}"
                            return {"id": int(peer_id), "title": title, "link": raw}, None
                        except Exception:
                            continue

                return None, "bot_cannot_check_invite_link_use_id_or_ensure_bot_is_member"
            except Exception as e:
                errors.append(f"invite_link_processing failed: {type(e).__name__}: {str(e)[:180]}")
                return None, "bot_cannot_check_invite_link_use_id_or_ensure_bot_is_member"

    if entity is None:
        chat_id = _extract_tme_c_chat_id(raw)
        if chat_id:
            try:
                entity = await client.get_entity(chat_id)
            except Exception as e:
                errors.append(f"tme_c get_entity failed: {type(e).__name__}: {str(e)[:180]}")
                return {"id": int(chat_id), "title": "کانال خصوصی", "link": raw}, "tme_c_parsed_no_entity"

    if not isinstance(entity, Channel):
        err = " | ".join(errors[-3:]) if errors else "not_a_channel_or_unresolvable"
        return None, err

    peer_id = utils.get_peer_id(entity)
    title = (getattr(entity, "title", None) or "").strip() or str(peer_id)

    username = getattr(entity, "username", None)
    link = f"https://t.me/{username}" if username else raw

    return {"id": int(peer_id), "title": title, "link": link}, None


async def botapi_create_invite_link(chat_id: int, *, name: str = "KK Lock") -> tuple[str | None, str | None]:
    """Create a new invite link for a chat/channel using Telegram Bot API."""
    if not BOT_TOKEN:
        return None, "missing_bot_token"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"
    payload = {"chat_id": int(chat_id), "name": name}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
        if not data.get("ok"):
            desc = str(data.get("description") or data)
            return None, f"botapi_error: {desc}"
        result = data.get("result") or {}
        link = result.get("invite_link")
        if not link:
            return None, "botapi_no_invite_link"
        return str(link), None
    except Exception as e:
        return None, f"botapi_exception: {type(e).__name__}: {str(e)[:180]}"

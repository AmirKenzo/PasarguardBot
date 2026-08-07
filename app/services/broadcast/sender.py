"""Telegram delivery helpers for broadcast jobs."""

from telethon import errors
from telethon.tl.types import MessageMediaWebPage

from app import Kenzo
from app.db.crud.user import UserCRUD, set_user_status
from app.db.models.broadcast import BroadcastJob
from app.logger import get_logger
from app.services.broadcast.markup import deserialize_buttons
from app.services.telegram.rich_message import RichMessageError, send_rich_message

logger = get_logger(__name__)

_NON_FILE_MEDIA_TYPES = (MessageMediaWebPage,)


def _message_text(msg) -> str:
    return msg.message or msg.text or ""


def _webpage_fallback_text(msg) -> str:
    media = msg.media
    if isinstance(media, MessageMediaWebPage) and media.webpage:
        webpage = media.webpage
        return getattr(webpage, "url", None) or getattr(webpage, "display_url", "") or ""
    return ""


def _build_copy_kwargs(msg, buttons) -> dict:
    """Build send_message kwargs for copying a source message as the bot."""
    text = _message_text(msg) or _webpage_fallback_text(msg)
    kwargs: dict = {"message": text, "buttons": buttons}
    if msg.entities:
        kwargs["formatting_entities"] = msg.entities

    media = msg.media
    if media is None or isinstance(media, _NON_FILE_MEDIA_TYPES):
        if isinstance(media, MessageMediaWebPage):
            kwargs["link_preview"] = True
        return kwargs

    kwargs["file"] = media
    return kwargs


def _sendable_album_media(msg):
    media = msg.media
    if media is None or isinstance(media, _NON_FILE_MEDIA_TYPES):
        return None
    return media


class BroadcastSender:
    """Send broadcast payloads and map Telegram delivery errors."""

    def __init__(self, user_crud: UserCRUD | None = None) -> None:
        self.user_crud = user_crud or UserCRUD()
        # Cache source messages / deserialized buttons once per job.
        self._source_messages: dict[int, list] = {}
        self._buttons_cache: dict[int, object] = {}

    def clear_job_cache(self, job_id: int) -> None:
        self._source_messages.pop(job_id, None)
        self._buttons_cache.pop(job_id, None)

    async def send_test(self, job: BroadcastJob, admin_id: int) -> tuple[bool, str]:
        """Send a draft broadcast payload to the admin who created it."""
        try:
            await self._send_payload(job, admin_id, log_prefix="test send")
            logger.info(f"Test message sent to admin {admin_id} for job {job.id}")
            return True, "✅ پیام تست ارسال شد!"
        except RichMessageError as exc:
            logger.error(f"Error sending test message: {exc}")
            return False, exc.message
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
            return False, "❌ خطا در ارسال پیام تست!"

    async def send_to_user(self, job: BroadcastJob, user_id: int) -> tuple[bool, str]:
        """
        Send message to a single user.

        Returns (success, status) where status is: ok, blocked, deleted, failed.
        """
        try:
            await self._send_payload(job, user_id, log_prefix=f"Job {job.id}")
            return True, "ok"
        except errors.UserIsBlockedError:
            logger.warning(f"🚫 [Job {job.id}] User ID {user_id} blocked the bot")
            if job.target_mode != "banned_users":
                await set_user_status(user_id, "BlockedBot")
            return False, "blocked"
        except errors.InputUserDeactivatedError:
            logger.warning(f"🗑️ [Job {job.id}] User ID {user_id} account deleted/deactivated")
            if job.target_mode != "banned_users":
                await set_user_status(user_id, "DeleteAccount")
            return False, "deleted"
        except errors.FloodWaitError:
            raise
        except Exception as e:
            logger.error(f"❌ [Job {job.id}] Error sending to user ID {user_id}: {type(e).__name__}: {e!s}")
            await self.handle_send_error(job, user_id, e)
            return False, "failed"

    async def handle_send_error(self, job: BroadcastJob, user_id: int, error: Exception) -> None:
        """Handle send errors and map to user.status if applicable."""
        if job.target_mode == "banned_users":
            return

        error_str = str(error).lower()
        if "blocked" in error_str or isinstance(error, errors.UserIsBlockedError):
            await set_user_status(user_id, "BlockedBot")
        elif "deactivated" in error_str or isinstance(error, errors.InputUserDeactivatedError):
            await set_user_status(user_id, "DeleteAccount")

    async def _get_source_messages(self, job_id: int, from_chat: int, message_ids: list[int]) -> list:
        cached = self._source_messages.get(job_id)
        if cached is not None:
            return cached
        msgs = await Kenzo.get_messages(from_chat, ids=message_ids)
        if not msgs:
            raise ValueError("Source broadcast message not found")
        self._source_messages[job_id] = list(msgs)
        return self._source_messages[job_id]

    def _get_buttons(self, job: BroadcastJob):
        cached = self._buttons_cache.get(job.id)
        if cached is not None or job.id in self._buttons_cache:
            return cached
        buttons = deserialize_buttons(job.payload_json.get("buttons"))
        self._buttons_cache[job.id] = buttons
        return buttons

    async def _copy_message_with_buttons(
        self, job: BroadcastJob, user_id: int, from_chat: int, message_ids: list[int]
    ) -> None:
        """Copy source message(s) as bot message with preserved inline keyboard."""
        msgs = await self._get_source_messages(job.id, from_chat, message_ids)
        buttons = self._get_buttons(job)

        if len(msgs) == 1:
            msg = msgs[0]
            if isinstance(msg.media, MessageMediaWebPage):
                # Web previews cannot be sent via file=; forward preserves the full card + buttons.
                await Kenzo.forward_messages(user_id, msg.id, from_chat, drop_author=True)
                return
            await Kenzo.send_message(user_id, **_build_copy_kwargs(msg, buttons))
            return

        files = [media for msg in msgs if (media := _sendable_album_media(msg))]
        caption = next((_message_text(msg) for msg in reversed(msgs) if _message_text(msg)), "") or ""
        if not caption:
            caption = _webpage_fallback_text(msgs[-1])
        entities = next((msg.entities for msg in reversed(msgs) if msg.entities), None)
        kwargs: dict = {"message": caption, "buttons": buttons}
        if files:
            kwargs["file"] = files if len(files) > 1 else files[0]
        elif isinstance(msgs[-1].media, MessageMediaWebPage):
            kwargs["link_preview"] = True
        if entities:
            kwargs["formatting_entities"] = entities
        await Kenzo.send_message(user_id, **kwargs)

    async def _send_payload(self, job: BroadcastJob, user_id: int, *, log_prefix: str) -> None:
        payload = job.payload_json
        is_forward = payload.get("is_forward", False)
        message_ids = payload.get("message_ids", [])
        from_chat = payload.get("from_chat")
        buttons = self._get_buttons(job)

        if message_ids and from_chat:
            if is_forward:
                await Kenzo.forward_messages(
                    user_id,
                    message_ids,
                    from_chat,
                    drop_author=not payload.get("keep_author", False),
                )
                return

            await self._copy_message_with_buttons(job, user_id, from_chat, message_ids)
            return

        if payload.get("text"):
            if payload.get("parse_mode") == "rich":
                await send_rich_message(user_id, payload["text"], buttons=buttons, rtl=True)
                return
            await Kenzo.send_message(user_id, payload.get("text", ""), buttons=buttons)
            return

        logger.error(f"❌ [{log_prefix}] No valid content in payload for user ID {user_id}: {payload}")
        raise ValueError("No valid broadcast payload content")

"""Send Telegram Rich Messages via MTProto (InputRichMessageMarkdown)."""

from __future__ import annotations

import random
import re
from urllib.parse import urlparse

from telethon import errors
from telethon.tl import functions, types

from app import Kenzo

RICH_MESSAGE_DOCS_URL = "https://core.telegram.org/bots/api#rich-message-formatting-options"

# https://core.telegram.org/bots/api#rich-message-limits
RICH_MESSAGE_MAX_BLOCKS = 500
RICH_MESSAGE_SAFE_MARGIN = 5
# Heading, summary, <details>, table header/separator, optional page footer.
USAGE_HISTORY_RICH_OVERHEAD_BLOCKS = 10
USAGE_HISTORY_PER_PAGE = RICH_MESSAGE_MAX_BLOCKS - USAGE_HISTORY_RICH_OVERHEAD_BLOCKS - RICH_MESSAGE_SAFE_MARGIN

_SUPPORTED_SCHEMES = frozenset({"http", "https", "tg", "mailto", "tel"})
_MARKDOWN_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
_MEDIA_EMBED_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MD_MARK_RE = re.compile(r"[*`]")


def rt(text) -> types.TypeRichText:
    """Plain RichText leaf for native blocks; strips stray markdown marker characters."""
    return types.TextPlain(text=_MD_MARK_RE.sub("", str(text)))


def rt_bold(text) -> types.TypeRichText:
    return types.TextBold(rt(text))


class RichMessageError(Exception):
    """Rich message could not be delivered (invalid URLs or Telegram rejection)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def is_valid_rich_message_url(url: str) -> bool:
    """Return True when Telegram accepts the URL as a rich inline / media target."""
    url = (url or "").strip()
    if not url:
        return False
    if url.startswith("#"):
        return len(url) > 1

    parsed = urlparse(url)
    if parsed.scheme in {"mailto", "tel"}:
        return True
    if parsed.scheme not in _SUPPORTED_SCHEMES:
        return False
    if parsed.scheme == "tg":
        return bool(parsed.netloc or parsed.path)
    return bool(parsed.netloc)


def sanitize_rich_markdown(markdown: str) -> str:
    """Drop markdown link/image targets Telegram rejects; keep visible label text."""

    def repl(match: re.Match[str]) -> str:
        label = match.group(2)
        url = match.group(3).strip()
        if is_valid_rich_message_url(url):
            return match.group(0)
        return label if label else url

    return _MARKDOWN_LINK_RE.sub(repl, markdown)


def strip_rich_media_embeds(markdown: str) -> str:
    """Remove `![](url)` blocks (keep alt text) — used when media URLs are rejected."""

    def repl(match: re.Match[str]) -> str:
        inner = match.group(0)
        link = _MARKDOWN_LINK_RE.match(inner)
        if not link:
            return ""
        label = link.group(2)
        url = link.group(3).strip()
        if label:
            return label
        return url

    return _MEDIA_EMBED_RE.sub(repl, markdown)


def prepare_rich_markdown(markdown: str) -> str:
    return sanitize_rich_markdown(markdown or "")


def build_input_rich_message(
    markdown: str,
    *,
    rtl: bool = True,
    noautolink: bool = True,
) -> types.InputRichMessageMarkdown:
    return types.InputRichMessageMarkdown(
        prepare_rich_markdown(markdown),
        rtl=rtl,
        noautolink=noautolink,
    )


def _rich_message_user_error() -> str:
    return (
        "ارسال Rich ناموفق بود: یک یا چند لینک/مدیا در متن برای تلگرام نامعتبر است.\n"
        "لینک‌های نسبی مثل `/command` یا مسیر فایل را حذف کنید؛ فقط http(s)://، tg://، mailto: و tel: مجازند.\n"
        "برای مدیا، URL باید فایل واقعی و قابل دسترس باشد (مثال‌های docs ممکن است کار نکنند)."
    )


async def _send_rich_request(
    chat_id: int,
    markdown: str,
    *,
    buttons,
    rtl: bool,
    noautolink: bool,
) -> None:
    reply_markup = Kenzo.build_reply_markup(buttons) if buttons else None
    await Kenzo(
        functions.messages.SendMessageRequest(
            peer=chat_id,
            message="",
            rich_message=types.InputRichMessageMarkdown(
                markdown,
                rtl=rtl,
                noautolink=noautolink,
            ),
            reply_markup=reply_markup,
            random_id=random.getrandbits(63),
        )
    )


def _is_rich_url_error(exc: BaseException) -> bool:
    return "RICH_MESSAGE_URL_INVALID" in str(exc)


async def send_rich_message(
    chat_id: int,
    markdown: str,
    *,
    buttons=None,
    rtl: bool = True,
    noautolink: bool = True,
) -> None:
    """Send a text-only rich message (empty `message`, content in `rich_message`)."""
    prepared = prepare_rich_markdown(markdown)

    try:
        await _send_rich_request(chat_id, prepared, buttons=buttons, rtl=rtl, noautolink=noautolink)
        return
    except errors.RPCError as exc:
        if not _is_rich_url_error(exc):
            raise
        without_media = strip_rich_media_embeds(prepared)
        if without_media != prepared:
            try:
                await _send_rich_request(
                    chat_id,
                    without_media,
                    buttons=buttons,
                    rtl=rtl,
                    noautolink=noautolink,
                )
                return
            except errors.RPCError as retry_exc:
                if not _is_rich_url_error(retry_exc):
                    raise
        raise RichMessageError(_rich_message_user_error()) from exc


async def edit_rich_message(
    event,
    markdown: str,
    *,
    buttons=None,
    rtl: bool = True,
    noautolink: bool = True,
) -> None:
    """Edit an existing message into a text-only rich message."""
    prepared = prepare_rich_markdown(markdown)
    msg = await event.get_message()
    reply_markup = Kenzo.build_reply_markup(buttons) if buttons else None
    await Kenzo(
        functions.messages.EditMessageRequest(
            peer=msg.peer_id,
            id=msg.id,
            message="",
            rich_message=types.InputRichMessageMarkdown(
                prepared,
                rtl=rtl,
                noautolink=noautolink,
            ),
            reply_markup=reply_markup,
        )
    )


async def edit_native_rich_message(
    event,
    blocks: list,
    *,
    buttons=None,
    rtl: bool = True,
    noautolink: bool = True,
    documents: list[types.InputDocument] | None = None,
    photos: list[types.InputPhoto] | None = None,
) -> None:
    """Edit an existing message into a native rich message built from explicit blocks (tables, button rows, …)."""
    msg = await event.get_message()
    reply_markup = Kenzo.build_reply_markup(buttons) if buttons else None
    await Kenzo(
        functions.messages.EditMessageRequest(
            peer=msg.peer_id,
            id=msg.id,
            message="",
            rich_message=types.InputRichMessage(
                blocks=blocks, rtl=rtl, noautolink=noautolink, documents=documents, photos=photos
            ),
            reply_markup=reply_markup,
        )
    )


async def send_native_rich_message(
    chat_id: int,
    blocks: list,
    *,
    buttons=None,
    rtl: bool = True,
    noautolink: bool = True,
    documents: list[types.InputDocument] | None = None,
    photos: list[types.InputPhoto] | None = None,
) -> None:
    """Send a new native rich message built from explicit blocks (tables, button rows, …).

    Native "Button Revolution" buttons (InlineButtonTypeCallback inside a PageButton) only exist
    inside InputRichMessage blocks — send_rich_message's InputRichMessageMarkdown has no block
    slot for them, so a first-time send with in-body buttons needs this instead of that.
    """
    reply_markup = Kenzo.build_reply_markup(buttons) if buttons else None
    await Kenzo(
        functions.messages.SendMessageRequest(
            peer=chat_id,
            message="",
            rich_message=types.InputRichMessage(
                blocks=blocks, rtl=rtl, noautolink=noautolink, documents=documents, photos=photos
            ),
            reply_markup=reply_markup,
            random_id=random.getrandbits(63),
        )
    )

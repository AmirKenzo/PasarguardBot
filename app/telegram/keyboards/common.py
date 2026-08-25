"""Shared Telegram button builders and style helpers."""

import re

from telethon import Button
from telethon.tl.types import (
    ButtonTypeDefault,
    ButtonTypeSimpleWebView,
    InlineButtonTypeCallback,
    InlineButtonTypeCopy,
    InlineButtonTypeUrl,
    InlineButtonTypeWebView,
    KeyboardButton,
    KeyboardButtonStyle,
    KeyboardInlineButton,
    MessageEntityCustomEmoji,
)

from app.db.crud.keyboards import KeyboardButtonCRUD


def create_button(text):
    # logger.debug("Create text button: %s", text)
    return Button.text(text=text, resize=True)


# --------------------------
# "Glass" button styling
# --------------------------
# Telegram buttons don't support real translucency; we emulate a "glassy" look
# using consistent brackets + an ice icon.
_GLASS_L = "「"
_GLASS_R = "」"
_GLASS_ICON = ""


def glass_text(label: str, *, icon: str = _GLASS_ICON) -> str:
    """Return a consistent 'glassy' label for buttons."""
    label = (label or "").strip()
    if not label:
        return f"{_GLASS_L}{_GLASS_ICON}{_GLASS_R}"
    return f"{_GLASS_L}{icon} {label}{_GLASS_R}"


def glass_text_button(label: str, *, resize: bool = True):
    return Button.text(text=glass_text(label), resize=resize)


def glass_inline_button(label: str, *, data: str):
    return Button.inline(glass_text(label), data=data)


def glass_url_button(label: str, *, url: str):
    return Button.url(glass_text(label), url=url)


KEYBOARD_CONFIG_STEPS = {
    "keyboard_btn_set_icon",
    "help_btn_set_icon",
    "help_download_app_config_set_icon",
}


def is_keyboard_config_step(step: str | None) -> bool:
    if not step:
        return False
    return (
        step.startswith("edit_keyboard:")
        or step.startswith("help_btn_")
        or step.startswith("help_download_app_config_")
        or step.startswith("help_download_app_target_")
        or step.startswith("help_dl_tgt_")
        or step in KEYBOARD_CONFIG_STEPS
    )


def is_wizard_step(step: str | None) -> bool:
    """True when user/admin is inside a multi-step flow — skip global menu handlers."""
    if not step:
        return False
    if is_keyboard_config_step(step):
        return True
    if step.startswith(("mb_", "md_")):
        return True
    return step in {"sendSupport", "support"}


def extract_custom_emoji_document_id(message) -> int | None:
    """Extract the first premium emoji document_id from a message, with numeric fallback."""
    for attr_name in ("entities", "formatting_entities"):
        for entity in getattr(message, attr_name, None) or []:
            if isinstance(entity, MessageEntityCustomEmoji) or hasattr(entity, "document_id"):
                return int(entity.document_id)

    text = (getattr(message, "text", None) or getattr(message, "message", None) or "").strip()
    for pattern in (r"emoji/(\d+)", r"tg://emoji\?id=(\d+)"):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    if text.isdigit():
        return int(text)

    media = getattr(message, "media", None)
    document = getattr(media, "document", None)
    if document and getattr(document, "id", None):
        for attr in getattr(document, "attributes", None) or []:
            if attr.__class__.__name__ == "DocumentAttributeCustomEmoji":
                return int(document.id)
        if getattr(document, "mime_type", "") == "application/x-tgsticker":
            return int(document.id)
    return None


def build_telegram_button_style(style: str | None, icon: int | None):
    if style and style not in ("primary", "danger", "success"):
        return None

    style_kwargs = {}
    if style:
        style_kwargs.update(
            {
                "primary": {"bg_primary": True},
                "danger": {"bg_danger": True},
                "success": {"bg_success": True},
            }[style]
        )
    if icon is not None:
        style_kwargs["icon"] = int(icon)
    return KeyboardButtonStyle(**style_kwargs) if style_kwargs else None


def _normalize_callback_data(data) -> bytes:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    return str(data).encode("utf-8")


def styled_callback_button(text: str, data, style_obj=None):
    payload = _normalize_callback_data(data)
    return KeyboardInlineButton(text=text, type=InlineButtonTypeCallback(data=payload), style=style_obj)


def styled_copy_button(text: str, copy_text: str, style_obj=None):
    return KeyboardInlineButton(text=text, type=InlineButtonTypeCopy(copy_text=copy_text), style=style_obj)


def styled_webview_button(text: str, url: str, style_obj=None):
    return KeyboardInlineButton(text=text, type=InlineButtonTypeWebView(url=url), style=style_obj)


def styled_url_button(text: str, url: str, style_obj=None):
    return KeyboardInlineButton(text=text, type=InlineButtonTypeUrl(url=url), style=style_obj)


def styled_simple_webview_button(text: str, url: str, style_obj=None):
    # Normal (non-inline) keyboard button, unlike styled_webview_button which is inline-only.
    return KeyboardButton(text=text, type=ButtonTypeSimpleWebView(url=url), style=style_obj)


def styled_reply_button(text: str, style_obj=None):
    return KeyboardButton(text=text, type=ButtonTypeDefault(), style=style_obj)


def _help_button_style(style: str | None, icon: int | None):
    """Build KeyboardButtonStyle from style name and optional icon."""
    return build_telegram_button_style(style, icon)


async def _get_keyboard_button_config(
    keyboard_crud: KeyboardButtonCRUD,
    key: str,
    default: str,
    *,
    default_style: str | None = None,
    default_icon: int | None = None,
) -> tuple[str, KeyboardButtonStyle | None]:
    button = await keyboard_crud.get_button(key)
    text = button.button_text if button and button.button_text else default
    clear_default_style = button is not None and button.button_style == ""
    style = None if clear_default_style else button.button_style if button and button.button_style else default_style
    if button and button.button_icon is not None:
        icon = button.button_icon
    elif clear_default_style:
        icon = None
    else:
        icon = default_icon
    return text, build_telegram_button_style(style, icon)


def _build_help_url_button(btn) -> KeyboardInlineButton | None:
    """Build help button: inline URL button with optional style, plain text (no glass)."""
    text = (btn.button_text or "").strip()
    url = (btn.button_url or "").strip()
    if not text or not url:
        return None
    style_obj = _help_button_style(btn.button_style, btn.button_icon)
    return KeyboardInlineButton(text=text, type=InlineButtonTypeUrl(url=url), style=style_obj)


def _build_help_button_telegram(btn):
    """Build one Telegram button from HelpButton (link URL or inline Download). Returns None if link empty."""
    if getattr(btn, "callback_key", None):
        style_obj = _help_button_style(getattr(btn, "button_style", None), getattr(btn, "button_icon", None))
        data = f"Download_{btn.callback_key}".encode()
        if style_obj:
            return styled_callback_button((btn.button_text or "").strip(), data, style_obj)
        return Button.inline((btn.button_text or "").strip(), data=f"Download_{btn.callback_key}")
    return _build_help_url_button(btn)

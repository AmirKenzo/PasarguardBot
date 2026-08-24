"""Help download apps: patterns, GitHub, manager, admin UI, sync."""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import secrets
from os.path import basename
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import httpx
from aiofasttelethonhelper import fast_upload
from telethon import Button
from telethon.errors import MessageNotModifiedError

from app import Kenzo
from app.db.crud.app_files import AppFileManager
from app.db.crud.help_buttons import HelpDownloadAppCRUD
from app.db.crud.log_channels import LogChannelManager
from app.logger import get_logger
from app.telegram.keyboards.common import _help_button_style, styled_callback_button
from config import GITHUB_TOKEN

logger = get_logger(__name__)


def _github_api_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


# --- patterns.py ---

VERSION_PLACEHOLDER = "{{VERSION}}"
SEGMENT_PLACEHOLDER = "{{SEGMENT}}"
_VERSION_RE = r"\d+(?:\.\d+)*"
_SEGMENT_RE = r"[^_]+"

HELP_TARGETS_GUIDE_FA = """📖 **راهنمای الگو و دکمه‌های دانلود**

**الگوی نام فایل (`%`):**
• `%` = یک بخش بین `_` (مثلاً نسخه `2.1.8`)
• `%.%.%` = همان نسخه کامل (مثل `2.1.8`) — برای نام‌هایی مثل:
  `v2rayNG_%.%.%_universal.apk` → `v2rayNG_2.1.8_universal.apk`
• اگر `%` نگذارید، همان متن به‌صورت **شامل بودن در اسم فایل** چک می‌شود (قدیمی)

**مثال برای V2rayNG:**
```
v2rayNG_%.%.%_universal.apk
v2rayNG_%.%.%_x86.apk
v2rayNG_%.%.%_arm64-v8a.apk
```

**دکمه دانلود:** برای هر نسخه/پلتفرم یک دکمه با متن، رنگ و آیکون جدا.
بعد از «🈸 آپدیت برنامه‌ها» فقط **tag جدید** عوض می‌شود؛ الگوها ثابت می‌مانند.

**افزودن اپ:** مخزن GitHub → **📥 دکمه‌های دانلود** → ➕ افزودن دکمه → متن دکمه → الگوها (هر خط یک الگو).
"""


def new_target_id() -> str:
    return secrets.token_hex(4)


def pattern_to_regex(pattern: str) -> re.Pattern[str]:
    p = (pattern or "").strip()
    if not p:
        return re.compile(r"^(?!x)x")
    p = re.sub(r"(?:%\.)+%", VERSION_PLACEHOLDER, p)
    p = p.replace("%.%.%", VERSION_PLACEHOLDER)
    p = re.sub(r"%", SEGMENT_PLACEHOLDER, p)
    parts: list[str] = []
    for chunk in re.split(r"(\{\{VERSION\}\}|\{\{SEGMENT\}\})", p):
        if chunk == VERSION_PLACEHOLDER:
            parts.append(_VERSION_RE)
        elif chunk == SEGMENT_PLACEHOLDER:
            parts.append(_SEGMENT_RE)
        elif chunk:
            parts.append(re.escape(chunk))
    return re.compile("^" + "".join(parts) + "$", re.IGNORECASE)


def matches_file_pattern(file_name: str, pattern: str) -> bool:
    pat = (pattern or "").strip()
    if not pat:
        return False
    if "%" in pat:
        try:
            return bool(pattern_to_regex(pat).match(file_name))
        except re.error:
            return False
    return pat.lower() in file_name.lower()


def normalize_target(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    tid = (raw.get("id") or "").strip() or f"t{index}"
    patterns = raw.get("patterns") or []
    if isinstance(patterns, str):
        patterns = [ln.strip() for ln in patterns.splitlines() if ln.strip()]
    patterns = [str(p).strip() for p in patterns if str(p).strip()]
    button_text = (raw.get("button_text") or raw.get("label") or f"دانلود {index + 1}").strip()
    style = raw.get("button_style")
    if style is not None:
        style = str(style).strip() or None
    icon = raw.get("button_icon")
    if icon is not None:
        try:
            icon = int(icon)
        except TypeError, ValueError:
            icon = None
    return {
        "id": tid,
        "button_text": button_text,
        "button_style": style,
        "button_icon": icon,
        "patterns": patterns,
    }


def normalize_targets(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, dict):
        if "targets" in raw and isinstance(raw["targets"], list):
            raw = raw["targets"]
        else:
            return []
    if not isinstance(raw, list):
        return []
    return [normalize_target(item, i) for i, item in enumerate(raw) if isinstance(item, dict)]


def categories_to_targets(categories: dict | None) -> list[dict[str, Any]]:
    if not categories:
        return []
    targets = []
    for idx, (label, keywords) in enumerate(categories.items()):
        kws = keywords if isinstance(keywords, list) else [keywords]
        patterns = [str(k).strip() for k in kws if str(k).strip()]
        if not patterns:
            continue
        short = label.replace("**", "").strip()
        if len(short) > 28:
            short = short[:25] + "…"
        targets.append(
            normalize_target(
                {
                    "id": f"cat{idx}",
                    "button_text": short,
                    "patterns": patterns,
                },
                idx,
            )
        )
    return targets


def get_download_targets(app: Any) -> list[dict[str, Any]]:
    stored = normalize_targets(getattr(app, "download_targets", None))
    if stored:
        return stored
    return categories_to_targets(getattr(app, "categories", None) or {})


def all_patterns_from_targets(targets: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in targets:
        for p in t.get("patterns") or []:
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def find_target_for_file(file_name: str, targets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for target in targets:
        for pattern in target.get("patterns") or []:
            if matches_file_pattern(file_name, pattern):
                return target
    return None


def target_by_id(targets: list[dict[str, Any]], target_id: str) -> dict[str, Any] | None:
    tid = (target_id or "").strip()
    for t in targets:
        if t.get("id") == tid:
            return t
    return None


def build_github_downloads_by_targets(
    assets: list[dict],
    targets: list[dict[str, Any]],
) -> dict[str, list[tuple[str, str, float]]]:
    """Map target id -> [(file_name, url, size_mb), ...] from GitHub release assets."""
    downloads: dict[str, list[tuple[str, str, float]]] = {t["id"]: [] for t in targets}
    assigned: set[str] = set()
    for asset in assets:
        file_name = asset.get("name") or ""
        if not file_name or file_name in assigned:
            continue
        target = find_target_for_file(file_name, targets)
        if not target:
            continue
        tid = target["id"]
        url = asset.get("browser_download_url") or ""
        size_mb = (asset.get("size") or 0) / (1024 * 1024)
        downloads[tid].append((file_name, url, size_mb))
        assigned.add(file_name)
    return {k: v for k, v in downloads.items() if v}


# --- defaults.py ---

LEGACY_APPS = {
    "happandroid": {
        "repo_owner": "Happ-proxy",
        "repo_name": "happ-android",
        "categories": {
            "📱 **اندروید مناسب تمام معماری ها**": ["Happ.apk"],
            "📱 **اندروید**": ["Happ.apk", "Happ_Beta.apk"],
        },
        "display_name": "Happ",
        "default_file": "Happ.apk",
        "start_param": "downloadhappandroid",
    },
    "v2rayng": {
        "repo_owner": "2dust",
        "repo_name": "v2rayNG",
        "categories": {
            "📱 **اندروید مناسب تمام معماری ها**": ["universal.apk"],
            "📱 **اندروید**": ["armeabi-v7a.apk", "arm64-v8a.apk", "_x86.apk", "_x86_64.apk"],
        },
        "display_name": "V2rayNG",
        "default_file": "universal.apk",
        "start_param": "downloadv2rayngandroid",
    },
    "hiddifyapp": {
        "repo_owner": "hiddify",
        "repo_name": "hiddify-app",
        "categories": {
            "📱 **اندروید**": ["Android-universal.apk", "Android-arm7.apk", "Android-arm64.apk"],
            "💻 **ویندوز**": ["Hiddify-Windows-Setup-x64.exe", "Hiddify-Windows-Setup-x64.Msix"],
            "🍎 **مک**": ["Hiddify-MacOS.dmg", "Hiddify-MacOS-Installer.pkg"],
            "🐧 **لینوکس**": ["Hiddify-Linux-x64.AppImage", "Hiddify-Debian-x64.deb"],
        },
        "display_name": "hiddify-app",
        "default_file": "Android-universal.apk",
        "start_param": "downloadhiddifyandroid",
    },
    "v2rayn": {
        "repo_owner": "2dust",
        "repo_name": "v2rayN",
        "categories": {
            "💻 **ویندوز**": [
                "v2rayN-windows-64-SelfContained.zip",
                "v2rayN-windows-64.zip",
                "v2rayN-windows-64-desktop.zip",
                "v2rayN-windows-arm64-desktop.zip",
            ],
            "🐧 **لینوکس**": ["v2rayN-linux-arm64.zip", "v2rayN-linux-64.zip"],
        },
        "display_name": "v2rayN",
        "default_file": "v2rayN-windows-64-desktop.zip",
        "start_param": "downloadv2raynpc",
    },
    "Throne": {
        "repo_owner": "throneproj",
        "repo_name": "Throne",
        "categories": {
            "💻 **ویندوز**": ["windows64.zip"],
            "🐧 **لینوکس**": ["debian-x64.deb", "linux64.zip"],
            "🍎 **مک**": ["macos-amd64.zip", "macos-arm64.zip"],
        },
        "display_name": "Throne",
        "default_file": "windows64.zip",
        "start_param": "downloadnekoraywindows",
    },
}

IOS_APP_URLS = {
    "streisand": "https://apps.apple.com/us/app/streisand/id6450534064",
    "fairvpn": "https://apps.apple.com/us/app/fair-vpn/id1533873488",
}

# Backward-compatible aliases
apps = LEGACY_APPS
ios_apps = IOS_APP_URLS

# --- github.py ---


async def fetch_latest_release_github(
    repo_owner: str, repo_name: str, custom_categories: dict[str, list] | None = None
) -> tuple[str, dict[str, list]] | None:
    if custom_categories is None:
        custom_categories = {
            "Android": ["arm64", "arm7", "x86_64", "apk"],
            "Windows": ["zip", "exe", "msix"],
            "Linux": ["AppImage", "deb", "rpm"],
            "Mac": ["dmg", "pkg"],
            "iOS": ["ipa"],
            "Universal": ["universal"],
        }

    _platform_extra = {
        "linux": ["linux", "deb", "rpm", "AppImage"],
        "لینوکس": ["linux", "deb", "rpm", "AppImage"],
        "mac": ["macos", "mac", "dmg", "pkg"],
        "مک": ["macos", "mac", "dmg", "pkg"],
        "windows": ["windows", "exe", "msix"],
        "ویندوز": ["windows", "exe", "msix"],
        "android": ["android", "apk"],
        "اندروید": ["android", "apk"],
        "ios": ["ios", "ipa"],
        "universal": ["universal"],
    }

    def expand_keywords(cat_name: str, keywords: list) -> list:
        k_lower = cat_name.lower()
        extra = []
        for key, vals in _platform_extra.items():
            if key in k_lower:
                extra.extend(vals)
                break
        combined = list(keywords) + extra
        return list(dict.fromkeys(combined))

    custom_categories = {cat: expand_keywords(cat, kw) for cat, kw in custom_categories.items()}

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    headers = _github_api_headers()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"خطا در دریافت اطلاعات: {e}")
            return None

    latest_release = response.json()
    _order = ("windows", "ویندوز", "linux", "لینوکس", "mac", "مک", "android", "اندروید", "ios", "universal")

    def _sort_key(item):
        k = item[0].lower()
        for i, s in enumerate(_order):
            if s in k:
                return i
        return 999

    sorted_categories = sorted(custom_categories.items(), key=_sort_key)
    downloads = {category: [] for category in custom_categories}

    for asset in latest_release["assets"]:
        file_name = asset["name"]
        download_url = asset["browser_download_url"]
        file_size_mb = asset["size"] / (1024 * 1024)
        for category, keywords in sorted_categories:
            if any(keyword.lower() in file_name.lower() for keyword in keywords):
                downloads[category].append((file_name, download_url, file_size_mb))
                break

    downloads = {k: v for k, v in downloads.items() if v}
    return latest_release["tag_name"], downloads


async def fetch_latest_release_github_targets(
    repo_owner: str,
    repo_name: str,
    targets: list,
) -> tuple[str, dict[str, list]] | None:
    norm_targets = normalize_targets(targets)
    if not norm_targets:
        return None

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    headers = _github_api_headers()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"خطا در دریافت اطلاعات: {e}")
            return None

    latest_release = response.json()
    by_id = build_github_downloads_by_targets(latest_release.get("assets") or [], norm_targets)
    if not by_id:
        return None

    display: dict[str, list] = {}
    for t in norm_targets:
        tid = t["id"]
        files = by_id.get(tid) or []
        if files:
            display[t.get("button_text") or tid] = files
    if not display:
        return None
    return latest_release["tag_name"], display


# --- manager.py ---

processing_callbacks: set[str] = set()


class AppDownloadManager:
    """English docstring for AppDownloadManager."""

    def __init__(self):
        self.app_file_manager = AppFileManager()

    async def download_and_upload(self, client, file_location, reply):
        """English docstring for download_and_upload."""
        filename = basename(urlparse(file_location).path)
        download_path = f"{filename}"
        try:
            async with aiohttp.ClientSession() as session, session.get(file_location) as response:
                response.raise_for_status()
                content = bytearray()
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    content.extend(chunk)
            await asyncio.to_thread(Path(download_path).write_bytes, content)
            x = await fast_upload(client, file_path=download_path)
            await client.send_file(reply.chat_id, x, caption="@BuyV2rayBot")
            await asyncio.to_thread(os.remove, download_path)
        except Exception as e:
            logger.error(f"Error downloading/uploading file: {e}")
            if await asyncio.to_thread(os.path.exists, download_path):
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(os.remove, download_path)
            raise

    async def download_and_upload_to_channel(
        self, client, file_url, chat_id, caption=None, reply_to=None, download_timeout_seconds=300
    ):
        """English docstring for download_and_upload_to_channel."""
        filename = basename(urlparse(file_url).path)
        download_path = f"{filename}"
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(file_url, timeout=aiohttp.ClientTimeout(total=download_timeout_seconds)) as response,
            ):
                response.raise_for_status()
                content = bytearray()
                while True:
                    chunk = await response.content.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    content.extend(chunk)
            await asyncio.to_thread(Path(download_path).write_bytes, content)

            # Upload to Telegram
            uploaded_file = await fast_upload(client, file_path=download_path)

            # Send file to channel
            send_file_kwargs = {
                "entity": chat_id,
                "file": uploaded_file,
            }
            if caption:
                send_file_kwargs["caption"] = caption
            if reply_to:
                send_file_kwargs["reply_to"] = reply_to

            sent_message = await client.send_file(**send_file_kwargs)

            # Clean up
            await asyncio.to_thread(os.remove, download_path)

            return sent_message
        except Exception as e:
            logger.error(f"Error downloading/uploading file to channel: {e}")
            if await asyncio.to_thread(os.path.exists, download_path):
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(os.remove, download_path)
            raise

    async def _resolve_help_app(self, app_key: str) -> tuple[dict | None, bool, str | None]:
        """Return (app_config, from_db, custom_message_only)."""
        db_app = await HelpDownloadAppCRUD().get_by_callback_key(app_key)
        if db_app:
            custom_msg = getattr(db_app, "custom_message", None) or None
            if custom_msg and not (db_app.repo_owner and db_app.repo_name):
                return None, True, custom_msg
            return (
                {
                    "repo_owner": db_app.repo_owner,
                    "repo_name": db_app.repo_name,
                    "categories": db_app.categories or {},
                    "download_targets": get_download_targets(db_app),
                    "display_name": db_app.button_text,
                    "default_file": db_app.default_file,
                    "ios_url": getattr(db_app, "ios_url", None) or None,
                },
                True,
                None,
            )
        if app_key in apps:
            legacy = apps[app_key]
            return legacy, False, None
        return None, False, None

    async def _prune_outdated_stored_files(self, app_key: str) -> list:
        stored_files = await self.app_file_manager.get_app_files_by_key(app_key)
        stored_tags = {af.tag_name for af in stored_files if af.tag_name}
        if len(stored_tags) > 1:
            latest_tag = self._resolve_latest_stored_tag(stored_files)
            if latest_tag:
                removed = await self.app_file_manager.delete_app_files_by_key_except_tag(app_key, latest_tag)
                if removed:
                    logger.info(
                        "Auto-removed %s outdated app file record(s) for %s (kept %s)",
                        removed,
                        app_key,
                        latest_tag,
                    )
                    stored_files = await self.app_file_manager.get_app_files_by_key(app_key)
        return stored_files

    async def _github_newer_than_stored(self, app: dict, stored_tag: str | None) -> str | None:
        if not stored_tag or not app.get("repo_owner") or not app.get("repo_name"):
            return None
        gh_result = await fetch_latest_release_github(
            app["repo_owner"], app["repo_name"], app.get("categories") or None
        )
        if not gh_result:
            return None
        github_tag, _ = gh_result
        if self._compare_release_tags(github_tag, stored_tag) > 0:
            return github_tag
        return None

    @staticmethod
    def _platform_short(label: str) -> str:
        t = label.replace("**", "").strip().lower()
        if "universal" in t or "تمام معماری" in t:
            return "همه معماری‌ها"
        if "اندروید" in t or "android" in t:
            return "اندروید"
        if "ویندوز" in t or "windows" in t:
            return "ویندوز"
        if "لینوکس" in t or "linux" in t:
            return "لینوکس"
        if "مک" in t or "mac" in t:
            return "مک"
        if "ios" in t:
            return "iOS"
        return label.replace("**", "").strip()

    async def send_app_list(self, event, app_key):
        """English docstring for send_app_list."""
        app, from_db, custom_msg = await self._resolve_help_app(app_key)
        if custom_msg:
            try:
                buttons = [[Button.inline("بازگشت", b"backTOhelp")]]
                await event.edit(custom_msg, buttons=buttons, link_preview=True)
            except MessageNotModifiedError:
                await event.answer()
            except Exception as e:
                logger.error(f"Error in send_app_list (text-only): {e}")
                await event.answer("❌ خطا در نمایش متن", alert=True)
            return
        if not app:
            await event.answer("❌ برنامه یافت نشد!", alert=True)
            return

        try:
            display_name = app.get("display_name", app_key.replace("_", " ").title())
            targets = app.get("download_targets") or categories_to_targets(app.get("categories"))
            stored_files = await self._prune_outdated_stored_files(app_key)
            stored_tag, downloads = self._build_downloads_from_db(stored_files, targets)
            from_stored = bool(downloads)
            github_newer_tag: str | None = None

            if not downloads:
                if targets:
                    result = await fetch_latest_release_github_targets(app["repo_owner"], app["repo_name"], targets)
                else:
                    result = await fetch_latest_release_github(
                        app["repo_owner"], app["repo_name"], app.get("categories") or None
                    )
                if result is None:
                    await event.edit("❌ دانلود در حال حاضر امکان‌پذیر نیست.")
                    return
                tag_name, downloads = result
                if not downloads:
                    await event.edit("❌ دانلود در حال حاضر امکان‌پذیر نیست.")
                    return
            else:
                tag_name = stored_tag or "ذخیره‌شده در ربات"
                github_newer_tag = await self._github_newer_than_stored(app, stored_tag)

            if from_stored:
                message = f"📦 **نسخه موجود {display_name}** — `{tag_name}`\n\n⬇️ **فایل‌های آماده ارسال در تلگرام:**\n\n"
                if github_newer_tag:
                    message += (
                        f"ℹ️ نسخه جدیدتر `{github_newer_tag}` در گیت‌هاب منتشر شده؛ "
                        f"فعلاً نسخه `{tag_name}` در ربات موجود است.\n\n"
                    )
            else:
                message = f"🎉 **آخرین نسخه {display_name} {tag_name} منتشر شد!** 🎉\n\n⬇️ **برای دانلود فایل‌ها:**\n\n"

            for target in targets:
                tid = target["id"]
                files = downloads.get(tid) if from_stored else downloads.get(target.get("button_text"))
                if not files and not from_stored:
                    for key, val in downloads.items():
                        if key == target.get("button_text"):
                            files = val
                            break
                if not files:
                    continue
                label = target.get("button_text") or tid
                message += f"**{label}**:\n"
                for file_name, url, size in files:
                    if from_stored:
                        message += f"  📄 `{file_name}` - {size:.2f}MB\n"
                    else:
                        message += f"  📄 `{file_name}` - {size:.2f}MB - [دانلود]({url})\n"
                message += "━━━━━━━━━━━━━\n"

            if from_stored:
                message += "\n💡 با زدن «دریافت نسخه» همان فایل‌های ذخیره‌شده برای شما ارسال می‌شود.\n"
            else:
                message += "\n💡 برای دریافت مستقیم در تلگرام، ادمین باید «🈸 آپدیت برنامه‌ها» را اجرا کند.\n"

            if from_db and app.get("ios_url"):
                message += f"\n🍎 **iOS:** [دانلود از اپ استور]({app['ios_url']})\n"
                message += "━━━━━━━━━━━━━\n"

            github_link = f"https://github.com/{app['repo_owner']}/{app['repo_name']}/releases"
            message += f"\n🌐 [مشاهده در گیت‌هاب]({github_link})"

            buttons = []
            if from_stored:
                for target in targets:
                    tid = target["id"]
                    if downloads.get(tid):
                        buttons.append([self._target_download_button(app_key, target)])
            buttons.append([Button.inline("بازگشت", b"backTOhelp")])

            try:
                await event.edit(message, buttons=buttons, link_preview=False)
            except MessageNotModifiedError:
                await event.answer()
            except Exception as e:
                logger.error(f"Error editing message in send_app_list: {e}")
                await event.answer("❌ خطا در نمایش لیست برنامه‌ها", alert=True)
        except Exception as e:
            logger.error(f"Error in send_app_list: {e}")
            await event.answer("❌ خطا در دریافت اطلاعات برنامه", alert=True)

    async def _get_app_config(self, app_key):
        """Resolve app config from DB or legacy apps dict. Returns dict or None."""
        db_app = await HelpDownloadAppCRUD().get_by_callback_key(app_key)
        if db_app:
            cats = db_app.categories or {}
            first_pat = (next(iter(next(iter(cats.values()))))) if cats else None
            return {
                "repo_owner": db_app.repo_owner,
                "repo_name": db_app.repo_name,
                "categories": cats,
                "download_targets": get_download_targets(db_app),
                "display_name": db_app.button_text,
                "default_file": db_app.default_file or first_pat,
            }
        if app_key in apps:
            return apps[app_key]
        return None

    @staticmethod
    def _file_matches_keywords(file_name: str, keywords: list) -> bool:
        if not keywords:
            return False
        lowered = file_name.lower()
        return any(kw.lower() in lowered for kw in keywords)

    @staticmethod
    def _normalize_release_tag(tag: str | None) -> tuple[int, ...]:
        if not tag:
            return (0,)
        cleaned = tag.strip().lstrip("vV")
        parts = re.findall(r"\d+", cleaned)
        return tuple(int(p) for p in parts) if parts else (0,)

    @classmethod
    def _compare_release_tags(cls, left: str | None, right: str | None) -> int:
        """Return positive if left is newer than right."""
        lv, rv = cls._normalize_release_tag(left), cls._normalize_release_tag(right)
        if lv == rv:
            return 0
        return 1 if lv > rv else -1

    @classmethod
    def _resolve_latest_stored_tag(cls, all_app_files: list) -> str | None:
        if not all_app_files:
            return None
        tagged = [af for af in all_app_files if af.tag_name]
        if not tagged:
            return None
        latest_tag = tagged[0].tag_name
        for af in tagged[1:]:
            if cls._compare_release_tags(af.tag_name, latest_tag) > 0:
                latest_tag = af.tag_name
        return latest_tag

    @classmethod
    def _filter_latest_version_files(cls, all_app_files: list) -> list:
        if not all_app_files:
            return []
        latest_tag = cls._resolve_latest_stored_tag(all_app_files)
        if latest_tag:
            latest_only = [af for af in all_app_files if af.tag_name == latest_tag]
            if latest_only:
                return latest_only
        return [all_app_files[0]]

    @staticmethod
    def _prefer_default_files(file_records: list, default_file: str | None) -> list:
        if not default_file or len(file_records) <= 1:
            return file_records
        matched = [af for af in file_records if default_file in af.file_name]
        if len(matched) <= 1:
            return matched or file_records
        non_fdroid = [af for af in matched if "fdroid" not in af.file_name.lower()]
        return non_fdroid or matched

    @staticmethod
    def _target_download_button(app_key: str, target: dict):
        text = (target.get("button_text") or "دریافت").strip()
        data = f"Download_{app_key}_t_{target['id']}".encode()
        style_obj = _help_button_style(target.get("button_style"), target.get("button_icon"))
        if style_obj:
            return styled_callback_button(text, data, style_obj)
        return Button.inline(text, data=f"Download_{app_key}_t_{target['id']}")

    def _build_downloads_from_db(self, all_app_files, targets: list[dict]) -> tuple[str | None, dict[str, list]]:
        """
        Group stored files by download_targets patterns.
        Returns (tag_name, {target_id: [(file_name, file_url, size_mb), ...]}).
        """
        all_app_files = self._filter_latest_version_files(all_app_files)
        if not all_app_files or not targets:
            return None, {}

        tag_name = self._resolve_latest_stored_tag(all_app_files)
        downloads: dict[str, list] = {}
        assigned: set[str] = set()

        for target in targets:
            tid = target["id"]
            patterns = target.get("patterns") or []
            matched = []
            for af in all_app_files:
                if af.file_name in assigned:
                    continue
                if any(matches_file_pattern(af.file_name, p) for p in patterns):
                    matched.append((af.file_name, af.file_url or "", af.file_size_mb or 0.0))
                    assigned.add(af.file_name)
            if matched:
                downloads[tid] = matched

        if not downloads and all_app_files:
            tid = targets[0]["id"]
            downloads[tid] = [(af.file_name, af.file_url or "", af.file_size_mb or 0.0) for af in all_app_files]
            tag_name = tag_name or all_app_files[0].tag_name

        return tag_name, downloads

    async def _send_stored_files(self, event, to_send: list) -> int:
        """Forward pre-uploaded files to the user. Returns count sent."""
        if hasattr(event, "delete"):
            with contextlib.suppress(Exception):
                await event.delete()

        sent_count = 0
        for app_file in to_send:
            try:
                await Kenzo.forward_messages(
                    entity=event.sender_id,
                    messages=[app_file.message_id],
                    from_peer=app_file.chat_id,
                    drop_author=True,
                )
                sent_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error sending file {app_file.file_name}: {e}")
        return sent_count

    async def download_app_file(self, event, app_key):
        """English docstring for download_app_file."""
        app = await self._get_app_config(app_key)
        if not app:
            error_msg = "❌ برنامه یافت نشد!"
            if hasattr(event, "answer"):
                await event.answer(error_msg, alert=True)
            else:
                await event.respond(error_msg)
            return

        try:
            display_name = app.get("display_name", app_key.replace("_", " ").title())
            default_file = app.get("default_file") or (
                next(iter(next(iter(app["categories"].values())))) if app.get("categories") else None
            )
            if not default_file:
                await event.answer("❌ تنظیم پیش‌فرض فایل برای این اپ وجود ندارد.", alert=True)
                return

            all_app_files = await self.app_file_manager.get_app_files_by_key(app_key)
            latest_files = self._filter_latest_version_files(all_app_files)

            app_file = None
            preferred = self._prefer_default_files(latest_files, default_file)
            for file_record in preferred:
                if default_file in file_record.file_name:
                    app_file = file_record
                    break

            if not app_file and preferred:
                app_file = preferred[0]
            elif not app_file and latest_files:
                app_file = latest_files[0]

            # If pre-uploaded file exists, send it without forward (no channel ID shown)
            if app_file:
                try:
                    # Delete the callback message first (only for CallbackQuery.Event)
                    if hasattr(event, "delete"):
                        with contextlib.suppress(Exception):
                            await event.delete()

                    # Forward the pre-uploaded file without showing channel ID (drop_author=True)
                    await Kenzo.forward_messages(
                        entity=event.sender_id,
                        messages=[app_file.message_id],
                        from_peer=app_file.chat_id,
                        drop_author=True,
                    )

                    # user_downloads[event.sender_id] = current_time
                    await event.respond(f"✅ برنامه {display_name} با موفقیت ارسال شد!")
                    return
                except Exception as e:
                    logger.error(f"Error sending pre-uploaded file: {e}")
                    # Fall through to download method if sending fails

            # Fallback to old method: download from GitHub
            first_category = next(iter(app["categories"].values()))
            result = await fetch_latest_release_github(
                app["repo_owner"], app["repo_name"], {next(iter(app["categories"].keys())): first_category}
            )

            if result is None:
                error_msg = "❌ خطا در دریافت اطلاعات از GitHub"
                if hasattr(event, "answer"):
                    await event.answer(error_msg, alert=True)
                else:
                    await event.respond(error_msg)
                return

            _tag_name, downloads = result

            download_url = None

            for _os_type, files in downloads.items():
                for file_name, url, _size in files:
                    if default_file in file_name:
                        download_url = url
                        break
                if download_url:
                    break

            if not download_url:
                error_msg = "❌ فایل مورد نظر یافت نشد."
                if hasattr(event, "answer"):
                    await event.answer(error_msg, alert=True)
                else:
                    await event.respond(error_msg)
                return

            # Delete the callback message first (only for CallbackQuery.Event)
            if hasattr(event, "delete"):
                with contextlib.suppress(Exception):
                    await event.delete()

            # Send download message
            reply = await event.respond(f"📥 درحال دانلود برنامه {display_name} ...")

            try:
                # user_downloads[event.sender_id] = current_time
                await self.download_and_upload(Kenzo, download_url, reply)
                await reply.delete()
                await event.respond(f"✅ برنامه {display_name} با موفقیت ارسال شد!")
            except Exception as e:
                logger.error(f"Error downloading app file: {e}")
                with contextlib.suppress(Exception):
                    await reply.delete()
                await event.respond("❌ خطا در دانلود فایل")
        except Exception as e:
            logger.error(f"Error in download_app_file: {e}")
            raise

    async def download_all_app_files(self, event, app_key):
        """English docstring for download_all_app_files."""
        app = await self._get_app_config(app_key)
        if not app:
            error_msg = "❌ برنامه یافت نشد!"
            if hasattr(event, "answer"):
                await event.answer(error_msg, alert=True)
            else:
                await event.respond(error_msg)
            return

        try:
            display_name = app.get("display_name", app_key.replace("_", " ").title())

            all_app_files = await self.app_file_manager.get_app_files_by_key(app_key)
            latest_files = self._filter_latest_version_files(all_app_files)

            if not latest_files:
                error_msg = "❌ فایلی در دیتابیس یافت نشد!"
                if hasattr(event, "answer"):
                    await event.answer(error_msg, alert=True)
                else:
                    await event.respond(error_msg)
                return

            if hasattr(event, "delete"):
                with contextlib.suppress(Exception):
                    await event.delete()

            sent_count = 0
            for app_file in latest_files:
                try:
                    # Forward file without showing channel ID (drop_author=True)
                    await Kenzo.forward_messages(
                        entity=event.sender_id,
                        messages=[app_file.message_id],
                        from_peer=app_file.chat_id,
                        drop_author=True,
                    )
                    sent_count += 1
                    # Small delay between sends to avoid rate limiting
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending file {app_file.file_name}: {e}")
                    continue

            # user_downloads[event.sender_id] = current_time

            if sent_count > 0:
                await event.respond(f"✅ {sent_count} نسخه از برنامه {display_name} با موفقیت ارسال شد!")
            else:
                await event.respond("❌ خطا در ارسال فایل‌ها")
        except Exception as e:
            logger.error(f"Error in download_all_app_files: {e}")
            if hasattr(event, "answer"):
                await event.answer("❌ خطا در ارسال فایل‌ها", alert=True)
            else:
                await event.respond("❌ خطا در ارسال فایل‌ها")

    async def download_app_files_by_category(self, event, app_key: str, category_index: int):
        """Legacy index-based download (maps to download_targets order)."""
        app = await self._get_app_config(app_key)
        if not app:
            if hasattr(event, "answer"):
                await event.answer("❌ برنامه یافت نشد!", alert=True)
            else:
                await event.respond("❌ برنامه یافت نشد!")
            return
        targets = app.get("download_targets") or categories_to_targets(app.get("categories"))
        if category_index < 0 or category_index >= len(targets):
            if hasattr(event, "answer"):
                await event.answer("❌ دستهٔ انتخابی معتبر نیست.", alert=True)
            return
        await self.download_app_files_by_target(event, app_key, targets[category_index]["id"])

    async def download_app_files_by_target(self, event, app_key: str, target_id: str):
        """Send stored files matching one download_targets button."""
        app = await self._get_app_config(app_key)
        if not app:
            if hasattr(event, "answer"):
                await event.answer("❌ برنامه یافت نشد!", alert=True)
            else:
                await event.respond("❌ برنامه یافت نشد!")
            return
        if hasattr(event, "answer"):
            with contextlib.suppress(Exception):
                await event.answer("⏳ در حال ارسال فایل...")
        try:
            display_name = app.get("display_name", app_key.replace("_", " ").title())
            targets = app.get("download_targets") or categories_to_targets(app.get("categories"))
            target = target_by_id(targets, target_id)
            if not target:
                if hasattr(event, "answer"):
                    await event.answer("❌ دکمه دانلود یافت نشد.", alert=True)
                return

            all_app_files = await self.app_file_manager.get_app_files_by_key(app_key)
            latest_files = self._filter_latest_version_files(all_app_files)
            if not latest_files:
                msg = "❌ این برنامه هنوز در ربات ذخیره نشده.\nلطفاً از ادمین بخواهید «🈸 آپدیت برنامه‌ها» را اجرا کند."
                if hasattr(event, "answer"):
                    await event.answer(msg, alert=True)
                else:
                    await event.respond(msg)
                return

            patterns = target.get("patterns") or []
            to_send = [af for af in latest_files if any(matches_file_pattern(af.file_name, p) for p in patterns)]
            if len(to_send) > 1 and len(patterns) == 1 and "%" in (patterns[0] or ""):
                to_send = self._prefer_default_files(to_send, app.get("default_file"))

            stored_tag = self._resolve_latest_stored_tag(latest_files)
            sent_count = await self._send_stored_files(event, to_send)
            if sent_count > 0:
                btn_label = target.get("button_text") or target_id
                version_note = f" (نسخه `{stored_tag}`)" if stored_tag else ""
                await event.respond(
                    f"✅ {sent_count} فایل **{btn_label}**{version_note} برای **{display_name}** ارسال شد."
                )
                return

            await event.respond(
                "❌ ارسال فایل از کانال ذخیره‌سازی ممکن نشد. ادمین را از دسترسی ربات به کانال فایل‌ها مطلع کنید."
            )
        except Exception as e:
            logger.error(f"Error in download_app_files_by_target: {e}")
            if hasattr(event, "answer"):
                await event.answer("❌ خطا در ارسال فایل‌ها", alert=True)
            else:
                await event.respond("❌ خطا در ارسال فایل‌ها")


# Create a global instance for backward compatibility
app_download_manager = AppDownloadManager()


# Backward compatibility functions
async def download_and_upload(client, file_location, reply):
    """Backward compatibility wrapper"""
    return await app_download_manager.download_and_upload(client, file_location, reply)


async def download_app_file(event, app_key):
    """Backward compatibility wrapper"""
    return await app_download_manager.download_app_file(event, app_key)


async def send_app_list(event, app_key):
    """Backward compatibility wrapper"""
    return await app_download_manager.send_app_list(event, app_key)


# --- admin_ui.py ---


def create_download_app_config_submenu(app_id: int, app) -> list:
    is_github = app and (app.repo_owner or app.repo_name)
    is_text_only = app and getattr(app, "custom_message", None)
    rows = [
        [Button.inline("✏️ متن دکمه", data=f"help_download_app_config_edit_text:{app_id}")],
        [
            Button.inline("آبی", data=f"help_download_app_config_color:{app_id}:primary"),
            Button.inline("سبز", data=f"help_download_app_config_color:{app_id}:success"),
            Button.inline("قرمز", data=f"help_download_app_config_color:{app_id}:danger"),
            Button.inline("—", data=f"help_download_app_config_color:{app_id}:none"),
        ],
        [Button.inline("🖼 آیکون", data=f"help_download_app_config_icon:{app_id}")],
        [Button.inline("🧹 حذف آیکون", data=f"help_download_app_config_icon_clear:{app_id}")],
    ]
    if is_github:
        rows.append([Button.inline("📥 دکمه‌های دانلود (الگو)", data=f"help_download_app_targets:{app_id}")])
        rows.append([Button.inline("📦 مخزن (GitHub)", data=f"help_download_app_config_repo:{app_id}")])
        rows.append([Button.inline("🍎 لینک iOS", data=f"help_download_app_config_ios:{app_id}")])
    if is_text_only:
        rows.append([Button.inline("📝 متن پیام", data=f"help_download_app_config_custom_msg:{app_id}")])
    rows.append([Button.inline("🔙 بازگشت", data="help_download_apps_manage")])
    return rows


async def build_apps_manage_list_rows() -> list:
    crud = HelpDownloadAppCRUD()
    apps_list = await crud.get_all()
    rows = []
    for app in apps_list:
        rows.append(
            [
                Button.inline(f"📱 {app.button_text}", data=f"help_download_app_config:{app.id}"),
                Button.inline("🗑", data=f"help_download_app_del:{app.id}"),
            ]
        )
    rows.append([Button.inline("➕ افزودن اپ", data="help_download_app_add")])
    rows.append([Button.inline("📝 متن/لینک فقط", data="help_download_app_add_text")])
    rows.append([Button.inline("📋 اپ‌های پیش‌فرض", data="help_download_app_add_defaults")])
    rows.append([Button.inline("🔙 بازگشت", data="back_to_help_settings")])
    return rows


async def fetch_app(app_id: int):
    return await HelpDownloadAppCRUD().get_by_id(app_id)


async def load_targets(app_id: int) -> list[dict]:
    app = await fetch_app(app_id)
    if not app:
        return []
    return get_download_targets(app)


async def save_targets(app_id: int, targets: list[dict]) -> bool:
    normalized = normalize_targets(targets)
    return await HelpDownloadAppCRUD().update(app_id, download_targets=normalized)


async def append_target(app_id: int, button_text: str, patterns: list[str]) -> bool:
    targets = await load_targets(app_id)
    targets.append(
        normalize_target(
            {
                "id": new_target_id(),
                "button_text": button_text,
                "patterns": patterns,
            },
            len(targets),
        )
    )
    return await save_targets(app_id, targets)


async def update_target(app_id: int, target_id: str, **fields) -> bool:
    targets = await load_targets(app_id)
    updated = []
    found = False
    for t in targets:
        if t.get("id") == target_id:
            found = True
            merged = {**t, **fields}
            if "patterns" in fields and isinstance(fields["patterns"], str):
                merged["patterns"] = [ln.strip() for ln in fields["patterns"].splitlines() if ln.strip()]
            updated.append(normalize_target(merged, len(updated)))
        else:
            updated.append(t)
    if not found:
        return False
    return await save_targets(app_id, updated)


async def delete_target(app_id: int, target_id: str) -> bool:
    targets = [t for t in await load_targets(app_id) if t.get("id") != target_id]
    return await save_targets(app_id, targets)


async def migrate_categories_to_targets(app_id: int) -> bool:
    app = await fetch_app(app_id)
    if not app or not app.categories:
        return False
    if normalize_targets(getattr(app, "download_targets", None)):
        return False
    targets = categories_to_targets(app.categories)
    return await save_targets(app_id, targets)


def targets_list_message(app, targets: list[dict]) -> str:
    lines = [f"📥 **دکمه‌های دانلود — {app.button_text}**\n"]
    if not targets:
        lines.append("هنوز دکمه‌ای تعریف نشده. «➕ افزودن دکمه» را بزنید.\n")
    else:
        for i, t in enumerate(targets, 1):
            pats = t.get("patterns") or []
            preview = ", ".join(f"`{p}`" for p in pats[:3])
            if len(pats) > 3:
                preview += f" (+{len(pats) - 3})"
            lines.append(f"{i}. **{t.get('button_text', '?')}** — {preview or 'بدون الگو'}\n")
    lines.append("\n" + HELP_TARGETS_GUIDE_FA)
    return "".join(lines)


def targets_list_buttons(app_id: int, targets: list[dict]) -> list:
    rows = []
    for t in targets:
        tid = t["id"]
        label = (t.get("button_text") or tid)[:24]
        rows.append(
            [
                Button.inline(f"✏️ {label}", data=f"help_download_app_target:{app_id}:{tid}"),
                Button.inline("🗑", data=f"help_download_app_target_del:{app_id}:{tid}"),
            ]
        )
    rows.append([Button.inline("➕ افزودن دکمه", data=f"help_download_app_target_add:{app_id}")])
    if not targets:
        rows.append([Button.inline("📋 تبدیل از categories قدیمی", data=f"help_download_app_target_migrate:{app_id}")])
    rows.append([Button.inline("🔙 بازگشت", data=f"help_download_app_config:{app_id}")])
    return rows


def target_edit_buttons(app_id: int, target_id: str) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"help_download_app_target_text:{app_id}:{target_id}")],
        [Button.inline("📄 الگوهای فایل", data=f"help_download_app_target_patterns:{app_id}:{target_id}")],
        [
            Button.inline("آبی", data=f"help_download_app_target_color:{app_id}:{target_id}:primary"),
            Button.inline("سبز", data=f"help_download_app_target_color:{app_id}:{target_id}:success"),
            Button.inline("قرمز", data=f"help_download_app_target_color:{app_id}:{target_id}:danger"),
            Button.inline("—", data=f"help_download_app_target_color:{app_id}:{target_id}:none"),
        ],
        [Button.inline("🖼 آیکون", data=f"help_download_app_target_icon:{app_id}:{target_id}")],
        [Button.inline("🧹 حذف آیکون", data=f"help_download_app_target_icon_clear:{app_id}:{target_id}")],
        [Button.inline("🗑 حذف دکمه", data=f"help_download_app_target_del:{app_id}:{target_id}")],
        [Button.inline("🔙 بازگشت", data=f"help_download_app_targets:{app_id}")],
    ]


def patterns_edit_hint(target: dict) -> str:
    current = "\n".join(target.get("patterns") or []) or "(خالی)"
    return (
        f"📄 **الگوهای فایل — {target.get('button_text', '')}**\n\n"
        f"الگوهای فعلی:\n```\n{current}\n```\n\n"
        "هر خط یک الگو. مثال:\n"
        "`v2rayNG_%.%.%_universal.apk`\n"
        "`v2rayNG_%.%.%_x86.apk`\n\n"
        "الگوی جدید را در یک پیام بفرستید (جایگزین می‌شود):"
    )


# --- sync.py ---


async def run_admin_app_files_sync(status_message) -> None:
    log_destination = await LogChannelManager().get_log_channel_destination("app_files")
    if not log_destination:
        await status_message.edit(
            "❌ ابتدا باید یک کانال لاگ برای فایل‌های برنامه تنظیم کنید.\n"
            "از طریق منوی ادمین > مدیریت لاگ‌ها > تنظیم کانال لاگ"
        )
        return
    log_chat_id = int(log_destination["chat_id"])
    log_topic_id = int(log_destination["topic_id"]) if log_destination.get("topic_id") else None

    app_file_manager = AppFileManager()
    apps_to_update = {}
    for a in await HelpDownloadAppCRUD().get_all():
        apps_to_update[a.callback_key] = {
            "repo_owner": a.repo_owner,
            "repo_name": a.repo_name,
            "categories": a.categories or {},
            "download_targets": get_download_targets(a),
            "display_name": a.button_text,
            "default_file": a.default_file,
        }

    if not apps_to_update:
        await status_message.edit(
            "❌ هیچ اپی در لیست نیست. از **تنظیمات راهنما** > مدیریت اپ‌های دانلود، اپ اضافه کنید یا «اپ‌های پیش‌فرض» را بزنید."
        )
        return

    total_files = 0
    success_count = 0
    error_count = 0
    skipped_count = 0
    error_messages = []
    current_app_index = 0
    total_apps = len(apps_to_update)

    for app_key, app in apps_to_update.items():
        try:
            current_app_index += 1
            display_name = app.get("display_name", app_key)
            await status_message.edit(
                f"🔄 **در حال بروزرسانی فایل‌های برنامه‌ها...**\n\n"
                f"📦 **برنامه فعلی:** {display_name}\n"
                f"📊 **پیشرفت:** {current_app_index}/{total_apps}\n\n"
                f"⏳ در حال بررسی..."
            )

            targets = app.get("download_targets") or []
            if targets:
                result = await fetch_latest_release_github_targets(app["repo_owner"], app["repo_name"], targets)
            else:
                result = await fetch_latest_release_github(app["repo_owner"], app["repo_name"], app["categories"])

            if result is None:
                error_messages.append(f"❌ {display_name}: خطا در دریافت اطلاعات از GitHub")
                error_count += 1
                continue

            tag_name, downloads = result
            if not downloads:
                error_messages.append(f"❌ {display_name}: فایلی یافت نشد")
                error_count += 1
                continue

            existing_files = await app_file_manager.get_app_files_by_key(app_key)
            existing_files_dict = {f.file_name: f for f in existing_files}
            app_files_touched = 0

            for _os_type, files in downloads.items():
                for file_name, url, size_mb in files:
                    total_files += 1
                    try:
                        existing_file = existing_files_dict.get(file_name)
                        if existing_file and existing_file.tag_name == tag_name:
                            skipped_count += 1
                            app_files_touched += 1
                            continue

                        reply_msg = await Kenzo.send_message(
                            log_chat_id,
                            f"📥 در حال دانلود {file_name}...",
                            reply_to=log_topic_id,
                        )
                        try:
                            caption = f"📦 {display_name} - {file_name}\n🏷️ Tag: {tag_name}\n💾 Size: {size_mb:.2f} MB"
                            sent_message = await app_download_manager.download_and_upload_to_channel(
                                client=Kenzo,
                                file_url=url,
                                chat_id=log_chat_id,
                                caption=caption,
                                reply_to=log_topic_id,
                                download_timeout_seconds=300,
                            )
                        finally:
                            with contextlib.suppress(Exception):
                                await reply_msg.delete()

                        if existing_file:
                            await app_file_manager.update_app_file(
                                existing_file.id,
                                message_id=sent_message.id,
                                tag_name=tag_name,
                                file_size_mb=size_mb,
                            )
                        else:
                            await app_file_manager.create_app_file(
                                app_key=app_key,
                                file_name=file_name,
                                file_url=url,
                                message_id=sent_message.id,
                                chat_id=log_chat_id,
                                topic_id=log_topic_id,
                                tag_name=tag_name,
                                file_size_mb=size_mb,
                            )

                        success_count += 1
                        app_files_touched += 1
                    except Exception as e:
                        error_count += 1
                        error_messages.append(f"❌ {display_name} - {file_name}: {e}")
                        logger.error(f"Error updating app file {app_key}/{file_name}: {e}")
                        try:
                            if "reply_msg" in locals():
                                await reply_msg.delete()
                        except Exception:
                            pass

            if app_files_touched > 0:
                removed_old = await app_file_manager.delete_app_files_by_key_except_tag(app_key, tag_name)
                if removed_old:
                    logger.info(
                        "Removed %s old app file record(s) for %s (kept %s)",
                        removed_old,
                        app_key,
                        tag_name,
                    )

        except Exception as e:
            error_count += 1
            error_messages.append(f"❌ {app.get('display_name', app_key)}: {e}")
            logger.error(f"Error updating app {app_key}: {e}")

    summary = (
        f"✅ **بروزرسانی فایل‌های برنامه‌ها تکمیل شد**\n\n"
        f"📊 **آمار:**\n"
        f"• کل فایل‌ها: {total_files}\n"
        f"• دانلود شده: {success_count}\n"
        f"• رد شده (به‌روز): {skipped_count}\n"
        f"• خطا: {error_count}\n"
    )
    if error_messages:
        summary += "\n❌ **خطاها:**\n"
        for err in error_messages[:10]:
            summary += f"{err}\n"
        if len(error_messages) > 10:
            summary += f"\n... و {len(error_messages) - 10} خطای دیگر"

    await status_message.edit(summary)

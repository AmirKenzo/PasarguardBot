"""Manual usage-cap (GB) for Pay-as-you-go reseller accounts."""

from __future__ import annotations

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.logger import get_logger
from app.services.panels.admins import activate_reseller_admin, get_reseller_admin, suspend_reseller_admin
from app.services.reseller.logging import send_reseller_log
from app.utils.formatting.conversions import gigabytes_to_bytes
from app.utils.formatting.traffic import format_size

log = get_logger(__name__)

USAGE_CAPPED_STATUS = "usage_capped"


def parse_usage_cap_gb(raw: str) -> float | None:
    text = (raw or "").strip().replace(",", "").replace("،", "")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


async def apply_usage_cap_suspend(account, panel, *, reason: str, notify=None) -> bool:
    """Disable panel admin and mark account as usage-capped. Returns True if applied."""
    if account.status == USAGE_CAPPED_STATUS:
        return True
    if account.status in ("expired", "admin_paused"):
        return False
    try:
        await suspend_reseller_admin(panel, account.username)
    except Exception as exc:
        log.error("usage-cap suspend failed code=%s: %s", account.code, exc)
        return False

    await ResellerAccountCRUD().update_account(account.code, status=USAGE_CAPPED_STATUS)
    account.status = USAGE_CAPPED_STATUS
    if notify:
        await notify(account, reason)
    await send_reseller_log(
        "⛔️ تعلیق به‌خاطر سقف مصرف",
        account=account,
        extra_lines=[f"📌 <b>دلیل:</b> {reason}"],
    )
    return True


async def set_reseller_usage_cap(
    account,
    *,
    gigabytes: float | None,
    actor_id: int | None = None,
    actor_role: str | None = None,
) -> tuple[bool, str]:
    """Set or clear manual usage cap. ``gigabytes`` None/0 clears the cap."""
    if account.pricing_mode != "usage":
        return False, "سقف مصرف فقط برای پلن مصرفی (Pay as you go) است."

    if gigabytes is not None and gigabytes < 0:
        return False, "مقدار نامعتبر است."

    cap_bytes = None if gigabytes is None or gigabytes <= 0 else gigabytes_to_bytes(gigabytes)
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    used = 0
    admin = await get_reseller_admin(panel, account.username)
    if admin:
        used = int(getattr(admin, "used_traffic", 0) or 0)

    updates: dict = {"usage_cap_bytes": cap_bytes}
    reactivated = False
    capped_now = False

    if account.status == USAGE_CAPPED_STATUS:
        if cap_bytes is None or used < cap_bytes:
            try:
                await activate_reseller_admin(panel, account.username)
            except Exception as exc:
                log.error("usage-cap reactivate failed code=%s: %s", account.code, exc)
                return False, "خطا در فعال‌سازی مجدد پنل."
            updates["status"] = "active"
            reactivated = True
    elif account.status == "active" and cap_bytes is not None and used >= cap_bytes:
        try:
            await suspend_reseller_admin(panel, account.username)
        except Exception as exc:
            log.error("usage-cap immediate suspend failed code=%s: %s", account.code, exc)
            return False, "خطا در اعمال سقف مصرف."
        updates["status"] = USAGE_CAPPED_STATUS
        capped_now = True

    await ResellerAccountCRUD().update_account(account.code, **updates)
    account.usage_cap_bytes = cap_bytes
    if "status" in updates:
        account.status = updates["status"]

    if cap_bytes is None:
        msg = "سقف مصرف حذف شد."
        if reactivated:
            msg += " پنل دوباره فعال شد."
        log_title = "🧹 حذف سقف مصرف نمایندگی"
    else:
        msg = f"سقف مصرف روی {format_size(cap_bytes)} تنظیم شد."
        if capped_now:
            msg += " مصرف فعلی از سقف بیشتر است؛ پنل غیرفعال شد."
        elif reactivated:
            msg += " پنل دوباره فعال شد."
        log_title = "📦 تنظیم سقف مصرف نمایندگی"

    await send_reseller_log(
        log_title,
        account=account,
        actor_id=actor_id,
        actor_role=actor_role,
        extra_lines=[
            f"📥 <b>مصرف فعلی:</b> {format_size(used)}",
            f"🚦 <b>سقف جدید:</b> {format_size(cap_bytes) if cap_bytes else 'بدون محدودیت'}",
        ],
    )
    return True, msg


def usage_cap_menu_text(account, *, used_bytes: int = 0) -> str:
    cap = account.usage_cap_bytes
    cap_line = format_size(cap) if cap else "بدون محدودیت"
    status_note = ""
    if account.status == USAGE_CAPPED_STATUS:
        status_note = "\n\n⛔️ **پنل به‌خاطر رسیدن به سقف مصرف غیرفعال است.**\nبا افزایش یا حذف سقف، دوباره فعال می‌شود."
    return (
        f"**📦 محدودیت مصرف — `{account.username}`**\n\n"
        f"**📥 مصرف فعلی:** {format_size(used_bytes)}\n"
        f"**🚦 سقف دستی:** {cap_line}\n\n"
        "با رسیدن مصرف به این سقف، پنل نمایندگی و دسترسی یوزرهای آن غیرفعال می‌شود."
        f"{status_note}"
    )

"""Import an existing panel admin into bot reseller_accounts (no wallet charge)."""

from __future__ import annotations

from typing import Any

from pasarguard import AdminModify

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.db.models.reseller_accounts import ResellerAccount
from app.logger import get_logger
from app.services.billing.reseller_pricing import pricing_mode_label
from app.services.panels.admins import (
    compute_reseller_expiration,
    generate_admin_password,
    get_reseller_admin,
    modify_reseller_admin,
)
from app.services.panels.settings import get_panel_login_url
from app.services.reseller.logging import send_reseller_log
from app.utils.formatting.dates import Time_Date, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from app.utils.security.crypto import encrypt_data

log = get_logger(__name__)


def _admin_max_users(admin: Any) -> int | None:
    overrides = getattr(admin, "permission_overrides", None)
    if overrides is None:
        return None
    value = getattr(overrides, "max_users", None)
    if value is None:
        return None
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return None
    return parsed if parsed > 0 else None


def _admin_data_limit(admin: Any) -> int | None:
    try:
        value = int(getattr(admin, "data_limit", 0) or 0)
    except TypeError, ValueError:
        return None
    return value if value > 0 else None


def _admin_role_name(admin: Any) -> str | None:
    role = getattr(admin, "role", None)
    if role is None:
        return None
    name = getattr(role, "name", None)
    return str(name).strip() if name else None


def _admin_expire_label(admin: Any) -> str | None:
    for attr in ("expire", "expiration_time", "expire_date"):
        raw = getattr(admin, attr, None)
        if raw in (None, 0, "", "0"):
            continue
        try:
            return timestamp_to_persian_expiry(raw)
        except TypeError, ValueError, OSError:
            return str(raw)
    return None


def format_panel_admin_preview(admin: Any, *, panel_name: str) -> str:
    """Persian markdown preview of a live panel admin before import."""
    username = str(getattr(admin, "username", "") or "—")
    status = str(getattr(admin, "status", "") or "—")
    used = int(getattr(admin, "used_traffic", 0) or 0)
    data_limit = _admin_data_limit(admin)
    total_users = int(getattr(admin, "total_users", 0) or 0)
    max_users = _admin_max_users(admin)
    role_name = _admin_role_name(admin)
    note = str(getattr(admin, "note", "") or "").strip() or "—"
    expire_label = _admin_expire_label(admin)

    if data_limit:
        traffic_line = f"**📥 ترافیک:** {format_size(used)} / {format_size(data_limit)}"
    else:
        traffic_line = f"**📥 ترافیک:** {format_size(used)} / نامحدود"

    users_line = f"**👥 یوزرها:** {total_users} / {max_users}" if max_users else f"**👥 یوزرها:** {total_users}"

    lines = [
        f"**➕ افزودن ادمین موجود — {panel_name}**",
        "",
        f"**👤 نام کاربری:** `{username}`",
        f"**📊 وضعیت:** `{status}`",
    ]
    if role_name:
        lines.append(f"**🛡 نقش:** {role_name}")
    lines.extend(
        [
            traffic_line,
            users_line,
        ]
    )
    if expire_label:
        lines.append(f"**⏰ انقضا:** {expire_label}")
    lines.extend(
        [
            f"**📝 نوت فعلی:** `{note}`",
            "",
            "اگر اطلاعات درست است، آیدی عددی تلگرام کاربر را ارسال کنید.",
            "⚠️ آن کاربر باید قبلاً ربات را /start کرده باشد.",
        ]
    )
    return "\n".join(lines)


async def notify_imported_reseller_user(
    account: ResellerAccount,
    *,
    password: str,
    panel=None,
) -> bool:
    """DM activation credentials to the imported reseller. Returns True on success."""
    try:
        if panel is None:
            panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        panel_name = panel.name if panel else str(account.panel_code)
        login_url = get_panel_login_url(panel) if panel else "—"
        mode_label = pricing_mode_label(account.pricing_mode)
        text = (
            f"**🎉 نمایندگی پنل در ربات فعال شد!**\n\n"
            f"**📛 پنل:** {panel_name}\n"
            f"**#️⃣ کد نمایندگی:** `{account.code}`\n"
            f"**🌐 آدرس ورود:** `{login_url}`\n"
            f"**👤 نام کاربری:** `{account.username}`\n"
            f"**🔑 رمز عبور جدید:** `{password}`\n"
            f"**📋 نوع پلن:** {mode_label}\n\n"
            "از این پس می‌توانید نمایندگی را از بخش **«نمایندگی‌های من»** مدیریت کنید.\n"
            "⚠️ رمز فعلی پنل عوض شده است؛ آن را در جای امن ذخیره کنید."
        )
        await Kenzo.send_message(account.telegram_id, text, parse_mode="markdown")
        return True
    except Exception as exc:
        log.error(
            "notify imported reseller failed code=%s telegram_id=%s: %s",
            getattr(account, "code", None),
            getattr(account, "telegram_id", None),
            exc,
        )
        return False


async def import_existing_reseller_admin(
    *,
    panel_code: int,
    username: str,
    telegram_id: int,
    plan_id: int,
    actor_id: int | None = None,
) -> tuple[bool, str, ResellerAccount | None, str | None]:
    """Link an existing panel admin into reseller_accounts without creating a new admin."""
    username = (username or "").strip()
    if not username:
        return False, "نام کاربری معتبر نیست.", None, None

    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    if not panel:
        return False, "پنل یافت نشد.", None, None

    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan:
        return False, "پلن یافت نشد.", None, None
    if int(plan.panel_code) != int(panel_code):
        return False, "پلن متعلق به این پنل نیست.", None, None

    user = await UserCRUD().read_user(telegram_id)
    if not user:
        return False, f"کاربر {telegram_id} ربات را استارت نکرده است.", None, None

    existing = await ResellerAccountCRUD().get_by_panel_username(panel_code, username)
    if existing:
        return False, "این ادمین از قبل در ربات ثبت شده است.", None, None

    try:
        admin = await get_reseller_admin(panel, username)
    except Exception as exc:
        log.error("get_reseller_admin failed panel=%s username=%s: %s", panel_code, username, exc)
        return False, "خطا در دریافت ادمین از پنل.", None, None
    if not admin:
        return False, "ادمینی با این نام کاربری در پنل یافت نشد.", None, None

    new_password = generate_admin_password(username=username)
    try:
        await modify_reseller_admin(
            panel,
            username,
            AdminModify(password=new_password, note=str(telegram_id)),
        )
    except Exception as exc:
        log.error("modify_reseller_admin failed panel=%s username=%s: %s", panel_code, username, exc)
        return False, "خطا در به‌روزرسانی رمز/نوت ادمین در پنل.", None, None

    now = Time_Date()["stamp"]
    billing_state = {
        "started_at": now,
        "last_billed_at": now,
        "setup_fee": 0,
        "total_billed": 0,
    }
    expiration = compute_reseller_expiration(plan) if plan.pricing_mode == "fixed" else None
    account_code = await ResellerAccountCRUD().generate_unique_code()

    ok, result = await ResellerAccountCRUD().create_account(
        code=account_code,
        telegram_id=telegram_id,
        panel_code=int(panel_code),
        panel_admin_id=getattr(admin, "id", None),
        username=username,
        password_encrypted=encrypt_data(new_password),
        plan_id=plan.id,
        pricing_mode=plan.pricing_mode,
        data_limit=_admin_data_limit(admin),
        max_users=_admin_max_users(admin),
        purchased_volume=None,
        createtime=now,
        expiration_time=expiration,
        status="active",
        billing_state=ResellerAccountCRUD.dump_billing_state(billing_state),
    )
    if not ok:
        log.error("create_account failed after panel modify: %s", result)
        return False, "خطا در ثبت اکانت نمایندگی در ربات.", None, None

    account: ResellerAccount = result
    await send_reseller_log(
        "📥 افزودن ادمین موجود",
        account=account,
        actor_id=actor_id,
        actor_role="ادمین",
        extra_lines=[
            "🔗 <b>منبع:</b> ادمین موجود پنل (بدون ساخت ادمین جدید)",
            "💰 <b>شارژ کیف پول:</b> انجام نشد",
        ],
    )

    notified = await notify_imported_reseller_user(account, password=new_password, panel=panel)
    if notified:
        message = (
            f"✅ ادمین `{username}` با موفقیت به ربات اضافه شد.\n\n"
            f"**#️⃣ کد نمایندگی:** `{account.code}`\n"
            f"**🔑 رمز جدید:** `{new_password}`\n\n"
            "پیام فعال‌سازی برای کاربر ارسال شد."
        )
    else:
        message = (
            f"✅ ادمین `{username}` با موفقیت به ربات اضافه شد.\n\n"
            f"**#️⃣ کد نمایندگی:** `{account.code}`\n"
            f"**🔑 رمز جدید:** `{new_password}`\n\n"
            "⚠️ ارسال پیام به کاربر ناموفق بود؛ رمز را دستی به او بدهید."
        )
    return True, message, account, new_password

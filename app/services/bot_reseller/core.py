"""Bot reseller rules shared by the bot, the web app and the admin panel.

Everything that touches a reseller's users goes through here, so ownership, limits and the
"bill before you change it" rule are checked in one place.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from pasarguard import UserCreate, UserModify
from pasarguard.enums import UserDataLimitResetStrategy, UserStatus

from app.db.crud.bot_reseller import GB, BotResellerCRUD, load_group_ids
from app.db.crud.panels import PanelsManager
from app.db.models.bot_reseller import (
    DISABLED_BY_ADMIN,
    DISABLED_BY_RESELLER,
    DISABLED_BY_SYSTEM,
    GRANT_APPROVED,
    GRANT_PENDING,
    GRANT_REJECTED,
    GRANT_REVOKED,
    NAMING_TELEGRAM_ID,
    RESELLER_ACTIVE,
    RESELLER_FROZEN,
    RESELLER_SUSPENDED,
    BotReseller,
    BotResellerGrant,
    BotResellerService,
    BotResellerUser,
)
from app.logger import get_logger
from app.services.bot_reseller import notify, panel as panel_api
from app.utils.formatting.conversions import day_to_timestamp, gigabytes_to_bytes

log = get_logger(__name__)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,20}[a-z0-9]$")
NAME_RULE = "نام یوزر باید ۳ تا ۲۲ کاراکتر و فقط حروف کوچک انگلیسی، عدد و زیرخط باشد."
AFFIX_RE = re.compile(r"^[a-z0-9]{1,12}$")
AFFIX_RULE = "پیشوند و پسوند باید ۱ تا ۱۲ کاراکتر و فقط حروف کوچک انگلیسی و عدد باشد."
USERNAME_MAX = 32
NOT_FOUND = "یوزر یافت نشد."
NOT_RESELLER = "نمایندگی ربات برای شما فعال نیست."
ALREADY_PENDING = "درخواست این سرویس قبلاً ثبت شده و در انتظار بررسی است."


class Refused(Exception):
    """A request the rules turn down; the message goes back to the caller.

    ``key`` names an editable bot text the bot shows instead of the built-in message.
    """

    def __init__(self, message: str, *, key: str | None = None) -> None:
        super().__init__(message)
        self.key = key


@dataclass
class GrantTerms:
    """What a grant allows: its own values, or the service defaults. 0 means no limit."""

    price_per_gb: int
    max_users: int
    max_user_gb: float
    max_user_days: int


def affix_value(raw: str | None, telegram_id: int) -> str:
    """The text a stored prefix or suffix puts in a username."""
    return str(telegram_id) if raw == NAMING_TELEGRAM_ID else (raw or "")


def build_username(reseller: BotReseller, name: str) -> str:
    """The panel username for ``name``: prefix, name and suffix joined by underscores, empty parts skipped."""
    parts = (
        affix_value(reseller.username_prefix, reseller.telegram_id),
        name,
        affix_value(reseller.username_suffix, reseller.telegram_id),
    )
    return "_".join(part for part in parts if part)


def clean_affix(raw: str | None) -> str:
    """Validate an admin-entered prefix or suffix; returns the value to store."""
    value = (raw or "").strip().lower()
    if value in ("", NAMING_TELEGRAM_ID):
        return value
    if not AFFIX_RE.fullmatch(value):
        raise Refused(AFFIX_RULE)
    return value


async def set_naming(reseller_id: int, prefix: str | None, suffix: str | None) -> dict[str, str]:
    """Change how new usernames of a reseller are built; existing users keep their names."""
    crud = BotResellerCRUD()
    reseller = await crud.get_reseller(reseller_id)
    if reseller is None:
        raise Refused("نماینده یافت نشد.")
    values = {"username_prefix": clean_affix(prefix), "username_suffix": clean_affix(suffix)}
    if not await crud.update_reseller(reseller.id, **values):
        raise Refused("ذخیره تنظیمات ممکن نشد.")
    return values


def grant_terms(grant: BotResellerGrant, service: BotResellerService) -> GrantTerms:
    def pick(own, default):
        return default if own is None else own

    return GrantTerms(
        price_per_gb=int(pick(grant.price_per_gb, service.price_per_gb) or 0),
        max_users=int(pick(grant.max_users, service.max_users) or 0),
        max_user_gb=float(pick(grant.max_user_gb, service.max_user_gb) or 0),
        max_user_days=int(pick(grant.max_user_days, service.max_user_days) or 0),
    )


def _now() -> int:
    return int(time.time())


async def _panel(code: int):
    panel = await PanelsManager().get_panel_by_code(code=int(code))
    if panel is None:
        raise Refused("پنل این سرویس در دسترس نیست.")
    return panel


async def prices_for(reseller_id: int) -> dict[int, float]:
    """Price per GB of every service the reseller has (or had) a grant for."""
    crud = BotResellerCRUD()
    grants = await crud.list_grants(reseller_id=reseller_id)
    services = await crud.get_services(g.service_id for g in grants)
    return {
        g.service_id: float(grant_terms(g, services[g.service_id]).price_per_gb)
        for g in grants
        if g.service_id in services
    }


async def request_service(telegram_id: int, service_id: int) -> BotResellerGrant:
    crud = BotResellerCRUD()
    service = await crud.get_service(service_id)
    if service is None or not service.sale_enabled:
        raise Refused("این سرویس برای فروش فعال نیست.", key="bot_reseller_no_services")
    reseller = await crud.ensure_reseller(telegram_id)
    if reseller is None:
        raise Refused("ثبت درخواست ممکن نشد، دوباره تلاش کنید.")
    grant, reason = await crud.request_grant(reseller.id, service.id)
    if reason == GRANT_PENDING:
        raise Refused(ALREADY_PENDING)
    if reason == GRANT_APPROVED:
        raise Refused("این سرویس برای شما فعال است.")
    if grant is None:
        raise Refused("ثبت درخواست ممکن نشد، دوباره تلاش کنید.")
    await notify.log_event(
        "📨 درخواست نمایندگی ربات",
        [f"👤 <b>کاربر:</b> <code>{telegram_id}</code>", f"📦 <b>سرویس:</b> {service.name}"],
    )
    return grant


async def approve_grant(
    grant_id: int,
    *,
    actor_id: int,
    price_per_gb: int | None = None,
    max_users: int | None = None,
    max_user_gb: float | None = None,
    max_user_days: int | None = None,
) -> BotResellerGrant:
    crud = BotResellerCRUD()
    grant = await crud.get_grant(grant_id)
    if grant is None:
        raise Refused("درخواست یافت نشد.")
    if grant.status == GRANT_APPROVED:
        raise Refused("این درخواست قبلاً تأیید شده است.")
    service = await crud.get_service(grant.service_id)
    reseller = await crud.get_reseller(grant.reseller_id)
    if service is None or reseller is None:
        raise Refused("سرویس یا نماینده یافت نشد.")
    grant = await crud.decide_grant(
        grant.id,
        status=GRANT_APPROVED,
        actor_id=actor_id,
        reject_reason=None,
        price_per_gb=price_per_gb,
        max_users=max_users,
        max_user_gb=max_user_gb,
        max_user_days=max_user_days,
    )
    if grant is None:
        raise Refused("ذخیره تأیید ممکن نشد.")
    terms = grant_terms(grant, service)
    await notify.notify_reseller(
        reseller.telegram_id,
        "bot_reseller_approved",
        with_panel_button=True,
        service=service.name,
        price=f"{terms.price_per_gb:,}",
    )
    await notify.log_event(
        "✅ تأیید نمایندگی ربات",
        [
            f"👤 <b>کاربر:</b> <code>{reseller.telegram_id}</code>",
            f"📦 <b>سرویس:</b> {service.name}",
            f"💰 <b>قیمت هر گیگ:</b> <code>{terms.price_per_gb:,}</code>",
            f"👮 <b>تأیید:</b> <code>{actor_id}</code>",
        ],
    )
    return grant


async def reject_grant(grant_id: int, *, actor_id: int, reason: str | None) -> BotResellerGrant:
    crud = BotResellerCRUD()
    grant = await crud.get_grant(grant_id)
    if grant is None or grant.status != GRANT_PENDING:
        raise Refused("درخواست در انتظاری یافت نشد.")
    service = await crud.get_service(grant.service_id)
    reseller = await crud.get_reseller(grant.reseller_id)
    reason = (reason or "").strip()[:300] or None
    grant = await crud.decide_grant(grant.id, status=GRANT_REJECTED, actor_id=actor_id, reject_reason=reason)
    if grant is None:
        raise Refused("ذخیره رد درخواست ممکن نشد.")
    if reseller is not None:
        await notify.notify_reseller(
            reseller.telegram_id,
            "bot_reseller_rejected",
            service=service.name if service else "-",
            reason=reason or "-",
        )
    return grant


async def grant_manually(telegram_id: int, service_id: int, *, actor_id: int, **terms) -> BotResellerGrant:
    """Give a service without a request from the user (also reopens a rejected or revoked one)."""
    crud = BotResellerCRUD()
    service = await crud.get_service(service_id)
    if service is None:
        raise Refused("سرویس یافت نشد.")
    reseller = await crud.ensure_reseller(telegram_id)
    if reseller is None:
        raise Refused("ساخت نماینده ممکن نشد.")
    grant, reason = await crud.request_grant(reseller.id, service.id)
    if reason == GRANT_APPROVED:
        raise Refused("این سرویس برای این کاربر فعال است.")
    if grant is None:
        raise Refused("ثبت ممکن نشد.")
    return await approve_grant(grant.id, actor_id=actor_id, **terms)


async def revoke_grant(grant_id: int, *, actor_id: int) -> int:
    """Take a service away: bill its users' last traffic, delete them from the panel. Returns users removed."""
    crud = BotResellerCRUD()
    grant = await crud.get_grant(grant_id)
    if grant is None or grant.status != GRANT_APPROVED:
        raise Refused("سرویس فعالی برای گرفتن یافت نشد.")
    reseller = await crud.get_reseller(grant.reseller_id)
    if reseller is None:
        raise Refused("نماینده یافت نشد.")
    users = await crud.list_users(reseller.id, service_id=grant.service_id)
    removed = 0
    for user in users:
        await _delete_user(reseller, user)
        removed += 1
    await crud.decide_grant(grant.id, status=GRANT_REVOKED, actor_id=actor_id)
    service = await crud.get_service(grant.service_id)
    await notify.notify_reseller(reseller.telegram_id, "bot_reseller_revoked", service=service.name if service else "-")
    return removed


@dataclass
class ResellerContext:
    reseller: BotReseller
    grants: list[BotResellerGrant]
    services: dict[int, BotResellerService]

    def approved(self) -> list[BotResellerGrant]:
        return [g for g in self.grants if g.status == GRANT_APPROVED and g.service_id in self.services]

    def terms(self, service_id: int) -> GrantTerms | None:
        grant = next((g for g in self.approved() if g.service_id == int(service_id)), None)
        return grant_terms(grant, self.services[grant.service_id]) if grant else None


async def load_context(telegram_id: int, *, require_active_grant: bool = True) -> ResellerContext:
    crud = BotResellerCRUD()
    reseller = await crud.get_reseller_by_user(telegram_id)
    if reseller is None:
        raise Refused(NOT_RESELLER, key="bot_reseller_no_services")
    grants = await crud.list_grants(reseller_id=reseller.id)
    services = await crud.get_services(g.service_id for g in grants)
    ctx = ResellerContext(reseller=reseller, grants=grants, services=services)
    if require_active_grant and not ctx.approved():
        raise Refused(NOT_RESELLER, key="bot_reseller_no_services")
    return ctx


def is_active_reseller(ctx: ResellerContext | None) -> bool:
    return bool(ctx and ctx.approved())


async def _owned_user(ctx: ResellerContext, user_row_id: int) -> BotResellerUser:
    user = await BotResellerCRUD().get_user(user_row_id)
    if user is None or user.reseller_id != ctx.reseller.id or user.deleted_at is not None:
        raise Refused(NOT_FOUND)
    return user


def _check_can_change(ctx: ResellerContext) -> None:
    if ctx.reseller.status == RESELLER_SUSPENDED:
        raise Refused("نمایندگی شما توسط ادمین تعلیق شده است.")
    if ctx.reseller.status == RESELLER_FROZEN:
        raise Refused("موجودی کیف پول تمام شده؛ ابتدا کیف پول را شارژ کنید.")


def _check_limits(terms: GrantTerms, gb: float, days: int) -> None:
    if gb < 0 or days < 0:
        raise Refused("حجم و زمان نمی‌توانند منفی باشند.")
    if terms.max_user_gb:
        if gb == 0:
            raise Refused("حجم نامحدود برای این سرویس مجاز نیست.")
        if gb > terms.max_user_gb:
            raise Refused(f"حداکثر حجم هر یوزر {terms.max_user_gb:g} گیگ است.")
    if terms.max_user_days:
        if days == 0:
            raise Refused("زمان نامحدود برای این سرویس مجاز نیست.")
        if days > terms.max_user_days:
            raise Refused(f"حداکثر زمان هر یوزر {terms.max_user_days} روز است.")


async def settle_user(reseller: BotReseller, user: BotResellerUser, panel_user) -> None:
    """Bill the traffic of one user right now (before it is changed or deleted)."""
    if panel_user is None:
        return
    result = await BotResellerCRUD().apply_usage(
        reseller.id, {user.id: panel_api.traffic_counter(panel_user)}, await prices_for(reseller.id)
    )
    if not result.ok:
        raise Refused("ثبت مصرف این یوزر ممکن نشد، دوباره تلاش کنید.")


async def create_user(
    ctx: ResellerContext, *, service_id: int, name: str, gb: float, days: int, note: str | None
) -> tuple[BotResellerUser, str]:
    """Create a panel user under one of the reseller's services; returns the row and its subscription link."""
    _check_can_change(ctx)
    terms = ctx.terms(service_id)
    if terms is None:
        raise Refused("این سرویس برای شما فعال نیست.")
    name = (name or "").strip().lower()
    if not NAME_RE.fullmatch(name):
        raise Refused(NAME_RULE)
    _check_limits(terms, gb, days)

    crud = BotResellerCRUD()
    balance = (await crud.balances([ctx.reseller.telegram_id])).get(ctx.reseller.telegram_id, 0)
    if balance <= 0:
        raise Refused("برای ساخت یوزر موجودی کیف پول باید بیشتر از صفر باشد.")
    if terms.max_users and (await crud.count_users(ctx.reseller.id)).get(int(service_id), 0) >= terms.max_users:
        raise Refused(f"ظرفیت این سرویس ({terms.max_users} یوزر) پر است.")

    service = ctx.services[int(service_id)]
    panel = await _panel(service.panel_code)
    username = build_username(ctx.reseller, name)
    if len(username) > USERNAME_MAX:
        raise Refused(f"نام کامل یوزر ({username}) از {USERNAME_MAX} کاراکتر بیشتر است؛ نام کوتاه‌تری انتخاب کنید.")
    payload = UserCreate(
        username=username,
        group_ids=load_group_ids(service.group_ids),
        data_limit=gigabytes_to_bytes(gb) if gb else 0,
        expire=day_to_timestamp(days) if days else None,
        note=f"bot-reseller:{ctx.reseller.telegram_id}",
        data_limit_reset_strategy=UserDataLimitResetStrategy.NO_RESET,
    )
    try:
        created = await panel_api.create_user(panel, payload)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (400, 409, 422):
            raise Refused("این نام قبلاً استفاده شده؛ نام دیگری انتخاب کنید.") from exc
        raise
    row = await crud.add_user(
        reseller_id=ctx.reseller.id,
        service_id=service.id,
        panel_code=panel.code,
        panel_user_id=int(created.id),
        username=username,
        display_name=name,
        note=(note or "").strip()[:200] or None,
        baseline_bytes=panel_api.traffic_counter(created),
    )
    if row is None:
        try:
            await panel_api.remove_user(panel, int(created.id))
        except Exception as cleanup:
            log.error("bot reseller orphan cleanup failed panel_user=%s: %s", created.id, cleanup)
        raise Refused("ثبت یوزر ممکن نشد، دوباره تلاش کنید.")
    return row, panel_api.subscription_url(panel, created)


async def user_live(ctx: ResellerContext, user_row_id: int):
    user = await _owned_user(ctx, user_row_id)
    panel = await _panel(user.panel_code)
    return user, panel, await panel_api.get_user(panel, user.panel_user_id)


async def edit_user(ctx: ResellerContext, user_row_id: int, *, gb: float, days: int, note: str | None) -> None:
    _check_can_change(ctx)
    user = await _owned_user(ctx, user_row_id)
    terms = ctx.terms(user.service_id)
    if terms is None:
        raise Refused("این سرویس برای شما فعال نیست.")
    _check_limits(terms, gb, days)
    panel = await _panel(user.panel_code)
    await panel_api.modify_user(
        panel,
        user.panel_user_id,
        UserModify(data_limit=gigabytes_to_bytes(gb) if gb else 0, expire=day_to_timestamp(days) if days else 0),
    )
    await BotResellerCRUD().update_user(user.id, note=(note or "").strip()[:200] or None)


async def set_user_enabled(ctx: ResellerContext, user_row_id: int, *, enabled: bool) -> None:
    user = await _owned_user(ctx, user_row_id)
    if enabled:
        _check_can_change(ctx)
        if user.disabled_by == DISABLED_BY_ADMIN:
            raise Refused("این یوزر توسط ادمین غیرفعال شده است.")
    panel = await _panel(user.panel_code)
    await panel_api.modify_user(
        panel, user.panel_user_id, UserModify(status=UserStatus.ACTIVE if enabled else UserStatus.DISABLED)
    )
    await BotResellerCRUD().update_user(user.id, disabled_by=None if enabled else DISABLED_BY_RESELLER)


async def revoke_link(ctx: ResellerContext, user_row_id: int) -> str:
    _check_can_change(ctx)
    user = await _owned_user(ctx, user_row_id)
    panel = await _panel(user.panel_code)
    return panel_api.subscription_url(panel, await panel_api.revoke_subscription(panel, user.panel_user_id))


async def reset_user_usage(ctx: ResellerContext, user_row_id: int) -> None:
    """Refill the user's volume; billing follows the lifetime counter, so nothing paid is lost."""
    _check_can_change(ctx)
    user = await _owned_user(ctx, user_row_id)
    panel = await _panel(user.panel_code)
    await settle_user(ctx.reseller, user, await panel_api.get_user(panel, user.panel_user_id))
    await panel_api.reset_usage(panel, user.panel_user_id)


async def _delete_user(reseller: BotReseller, user: BotResellerUser) -> None:
    panel = await _panel(user.panel_code)
    await settle_user(reseller, user, await panel_api.get_user(panel, user.panel_user_id))
    await panel_api.remove_user(panel, user.panel_user_id)
    await BotResellerCRUD().update_user(user.id, deleted_at=_now())


async def delete_user_by_admin(reseller: BotReseller, user: BotResellerUser) -> None:
    await _delete_user(reseller, user)


async def delete_user(ctx: ResellerContext, user_row_id: int) -> None:
    if ctx.reseller.status == RESELLER_SUSPENDED:
        raise Refused("نمایندگی شما توسط ادمین تعلیق شده است.")
    await _delete_user(ctx.reseller, await _owned_user(ctx, user_row_id))


def user_cost(user: BotResellerUser, price_per_gb: float) -> int:
    """What the user's traffic cost at today's price (baseline is all traffic billed so far)."""
    return round(int(user.baseline_bytes or 0) / GB * float(price_per_gb))


async def _switch_users(reseller: BotReseller, *, enabled: bool, mark: str, only_marked: bool) -> int:
    """Turn the reseller's users off (marking them) or back on (only those carrying ``mark``)."""
    crud = BotResellerCRUD()
    users = await crud.list_users(reseller.id)
    users = [u for u in users if u.disabled_by == (mark if only_marked else None)]
    by_panel: dict[int, list[BotResellerUser]] = {}
    for user in users:
        by_panel.setdefault(user.panel_code, []).append(user)
    switched = 0
    for panel_code, panel_users in by_panel.items():
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if panel is None:
            continue
        await panel_api.bulk_set_enabled(panel, [u.panel_user_id for u in panel_users], enabled=enabled)
        await crud.set_disabled_by((u.id for u in panel_users), None if enabled else mark)
        switched += len(panel_users)
    return switched


async def freeze(reseller: BotReseller, balance: int) -> None:
    count = await _switch_users(reseller, enabled=False, mark=DISABLED_BY_SYSTEM, only_marked=False)
    await BotResellerCRUD().update_reseller(reseller.id, status=RESELLER_FROZEN, frozen_at=_now())
    await notify.notify_reseller(reseller.telegram_id, "bot_reseller_frozen", count=count, balance=f"{balance:,}")
    await notify.log_event(
        "⛔️ قطع نمایندگی ربات (موجودی)",
        [f"👤 <b>کاربر:</b> <code>{reseller.telegram_id}</code>", f"👥 <b>یوزر قطع‌شده:</b> <code>{count}</code>"],
    )


async def unfreeze(reseller: BotReseller) -> None:
    count = await _switch_users(reseller, enabled=True, mark=DISABLED_BY_SYSTEM, only_marked=True)
    await BotResellerCRUD().update_reseller(reseller.id, status=RESELLER_ACTIVE, frozen_at=None, warned_hours=None)
    await notify.notify_reseller(reseller.telegram_id, "bot_reseller_unfrozen", with_panel_button=True, count=count)


async def suspend(reseller_id: int) -> int:
    crud = BotResellerCRUD()
    reseller = await crud.get_reseller(reseller_id)
    if reseller is None:
        raise Refused("نماینده یافت نشد.")
    if reseller.status == RESELLER_SUSPENDED:
        raise Refused("این نماینده از قبل تعلیق است.")
    count = await _switch_users(reseller, enabled=False, mark=DISABLED_BY_ADMIN, only_marked=False)
    await crud.update_reseller(reseller.id, status=RESELLER_SUSPENDED)
    await notify.notify_reseller(reseller.telegram_id, "bot_reseller_suspended", count=count)
    return count


async def unsuspend(reseller_id: int) -> int:
    crud = BotResellerCRUD()
    reseller = await crud.get_reseller(reseller_id)
    if reseller is None or reseller.status != RESELLER_SUSPENDED:
        raise Refused("این نماینده تعلیق نیست.")
    count = await _switch_users(reseller, enabled=True, mark=DISABLED_BY_ADMIN, only_marked=True)
    await crud.update_reseller(reseller.id, status=RESELLER_ACTIVE)
    return count

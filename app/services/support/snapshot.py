"""Fresh service context for support tickets.

A support message is worth more when it arrives with the state of the service it
is about. This module turns one panel user into a :class:`ServiceSnapshot` (or
one bot-database row into a :class:`ServiceSnapshot` card), so the Telegram layer
only has to render.

Every panel call here is best-effort: a support message must still go through
when a panel is down, and the snapshot then reports ``panel_available=False``
instead of guessing a reason for the missing data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI

from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.services.billing.renewal import require_panel_userid
from app.services.panels.settings import panel_button_enabled, panel_has_volume_plans

logger = get_logger(__name__)

STATE_ACTIVE = "active"
STATE_EXPIRED = "expired"
STATE_LIMITED = "limited"
STATE_EXPIRED_LIMITED = "expired_limited"
STATE_DISABLED = "disabled"
STATE_ON_HOLD = "on_hold"
STATE_UNKNOWN = "unknown"

PANEL_ERROR_MISSING = "panel_missing"
PANEL_ERROR_NOT_IN_PANEL = "not_in_panel"
PANEL_ERROR_USERID_MISSING = "panel_userid_missing"
PANEL_ERROR_UNREACHABLE = "unreachable"

# Why the live panel data is missing, in the user's language. Never a guess about
# the service itself: these only describe the lookup that failed.
PANEL_ERROR_TEXTS = {
    PANEL_ERROR_MISSING: "پنل این سرویس در ربات ثبت نشده است",
    PANEL_ERROR_NOT_IN_PANEL: "این سرویس در پنل پیدا نشد",
    PANEL_ERROR_USERID_MISSING: "شناسهٔ کاربر در پنل ثبت نشده است",
    PANEL_ERROR_UNREACHABLE: "پنل در دسترس نیست",
}

STATE_LABELS: dict[str, tuple[str, str]] = {
    STATE_ACTIVE: ("🟢", "فعال"),
    STATE_EXPIRED: ("🔴", "زمان تمام شده"),
    STATE_LIMITED: ("🔴", "حجم تمام شده"),
    STATE_EXPIRED_LIMITED: ("🔴", "زمان و حجم تمام شده"),
    STATE_DISABLED: ("⛔️", "غیرفعال"),
    STATE_ON_HOLD: ("🔋", "در انتظار اولین اتصال"),
    STATE_UNKNOWN: ("⚪️", "نامشخص"),
}

# Short form for one button label; keeps the long wording for message bodies.
STATE_SHORT_LABELS: dict[str, tuple[str, str]] = {
    STATE_ACTIVE: ("🟢", "فعال"),
    STATE_EXPIRED: ("🔴", "منقضی"),
    STATE_LIMITED: ("🔴", "حجم تمام"),
    STATE_EXPIRED_LIMITED: ("🔴", "زمان و حجم تمام"),
    STATE_DISABLED: ("⛔️", "غیرفعال"),
    STATE_ON_HOLD: ("🔋", "در انتظار"),
    STATE_UNKNOWN: ("⚪️", "نامشخص"),
}

# Only these three native Telegram styles exist; everything else stays default.
STATE_STYLES: dict[str, str] = {
    STATE_ACTIVE: "success",
    STATE_ON_HOLD: "success",
    STATE_EXPIRED: "danger",
    STATE_LIMITED: "danger",
    STATE_EXPIRED_LIMITED: "danger",
}

EXPIRING_SOON = timedelta(days=3)
LOW_VOLUME_RATIO = 0.10
FAIR_USAGE_PLAN_TYPES = ("fair_usage", "fair")


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    """One service as the support flow sees it.

    ``panel_available=False`` means the live panel read failed (or was not
    attempted, for cards); the remaining fields then only carry what the bot
    stored itself.
    """

    code: int
    config_name: str
    panel_name: str
    panel_code: int | None
    owner_id: int | None
    is_test: bool
    state: str
    panel_available: bool
    panel_error: str | None = None
    expiration_time: int | None = None
    expire_at: datetime | None = None
    data_limit_bytes: int | None = None
    used_bytes: int | None = None
    remaining_bytes: int | None = None
    online_at: datetime | None = None
    expiring_soon: bool = False
    low_volume: bool = False
    can_renew: bool = False
    can_buy_volume: bool = False

    @property
    def unlimited(self) -> bool:
        """A zero data limit is Pasarguard's "no volume cap"."""
        return self.data_limit_bytes is not None and self.data_limit_bytes <= 0


@dataclass(frozen=True, slots=True)
class ServicesOverview:
    """All services of one user, from the bot database only (no panel calls)."""

    cards: tuple[ServiceSnapshot, ...]

    @property
    def total(self) -> int:
        return len(self.cards)

    def count(self, state: str) -> int:
        return sum(1 for card in self.cards if card.state == state)

    @property
    def expiring_soon(self) -> int:
        return sum(1 for card in self.cards if card.state == STATE_ACTIVE and card.expiring_soon)


def state_label(state: str) -> str:
    emoji, text = STATE_LABELS.get(state, STATE_LABELS[STATE_UNKNOWN])
    return f"{emoji} {text}"


def state_style(state: str) -> str | None:
    """Native Telegram button colour for a state; ``None`` keeps the default look."""
    return STATE_STYLES.get(state)


def card_state_text(card: ServiceSnapshot) -> str:
    """Short status label for a database-only card (picker row, admin list).

    A card cannot see a volume limit, so an active card that is close to expiry
    is flagged with the 🟡 warning instead of inventing a colour for it.
    """
    if card.state == STATE_ACTIVE and card.expiring_soon:
        return "🟡 نزدیک انقضا"
    emoji, text = STATE_SHORT_LABELS.get(card.state, STATE_SHORT_LABELS[STATE_UNKNOWN])
    return f"{emoji} {text}"


def panel_error_text(error: str | None) -> str:
    return PANEL_ERROR_TEXTS.get(error or "", PANEL_ERROR_TEXTS[PANEL_ERROR_UNREACHABLE])


def service_warnings(snapshot: ServiceSnapshot) -> list[str]:
    """Near-expiry / near-exhaustion notices.

    Telegram only has three native button styles, so the warning is a 🟡 line of
    text; the button keeps the colour of the service state instead of an invented
    yellow.
    """
    warnings = []
    if snapshot.expiring_soon:
        warnings.append("🟡 کمتر از ۳ روز تا پایان سرویس باقی مانده است.")
    if snapshot.low_volume:
        warnings.append("🟡 حجم باقی‌مانده کمتر از ۱۰٪ سرویس است.")
    return warnings


def service_belongs_to(service: Any | None, user_id: int | None) -> bool:
    """True only for a row owned by this Telegram user."""
    if service is None or user_id is None:
        return False
    return int(getattr(service, "id", 0) or 0) == int(user_id)


def coerce_datetime(value: Any) -> datetime | None:
    """Accept what Pasarguard returns for timestamps: datetime, unix int, or ISO text."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except OSError, OverflowError, ValueError:
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _now(now: datetime | None) -> datetime:
    now = now or datetime.now(UTC)
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


def _remaining_bytes(data_limit: int | None, used: int | None) -> int | None:
    if data_limit is None or data_limit <= 0:
        return None
    if used is None:
        return None
    return max(data_limit - used, 0)


def classify_state(
    *,
    panel_status: str | None,
    expire_at: datetime | None,
    data_limit_bytes: int | None,
    remaining_bytes: int | None,
    now: datetime,
) -> str:
    """Map a panel user to one of our states.

    The panel status and the raw numbers are both evidence: a service can be
    ``active`` on the panel while its own expiry timestamp has already passed.
    """
    status = (panel_status or "").strip().lower()
    if status == "disabled":
        return STATE_DISABLED

    unlimited = data_limit_bytes is not None and data_limit_bytes <= 0
    time_over = expire_at is not None and expire_at <= now
    volume_over = not unlimited and remaining_bytes is not None and remaining_bytes <= 0

    expired = time_over or status == "expired"
    limited = volume_over or status == "limited"

    if expired and limited:
        return STATE_EXPIRED_LIMITED
    if expired:
        return STATE_EXPIRED
    if limited:
        return STATE_LIMITED
    if status == "on_hold":
        return STATE_ON_HOLD
    if status == "active":
        return STATE_ACTIVE
    return STATE_UNKNOWN


def _expiring_soon(expire_at: datetime | None, now: datetime) -> bool:
    if expire_at is None:
        return False
    remaining = expire_at - now
    return timedelta(0) < remaining <= EXPIRING_SOON


def _low_volume(data_limit: int | None, remaining: int | None) -> bool:
    if data_limit is None or data_limit <= 0 or remaining is None:
        return False
    return 0 < remaining <= data_limit * LOW_VOLUME_RATIO


def default_action_flags(service: Any, panel: Any | None, settings: Any | None) -> tuple[bool, bool]:
    """(renew, buy volume) availability, matching the service-callback guards.

    A button that the guard would reject is worse than no button, so both sides
    read the same bot settings and per-panel button switches.
    """
    is_test = getattr(service, "is_test", False) is True
    if panel is None or is_test or settings is None:
        return False, False
    can_renew = bool(getattr(settings, "tamdid_mode", False) and panel_button_enabled(panel, "btn_tamdid"))
    can_buy_volume = bool(
        getattr(settings, "upg_mode", False)
        and panel_button_enabled(panel, "btn_hajm")
        and panel_has_volume_plans(panel)
    )
    return can_renew, can_buy_volume


async def service_uses_fair_usage_plan(service: Any) -> bool:
    """Fair-usage plans reset their own volume, so extra volume is not sold."""
    package_size = _as_int(getattr(service, "package_size", None))
    if not package_size or package_size <= 0:
        return False
    panel_code = _as_int(getattr(service, "in_panel", None))
    if panel_code is None:
        return False
    try:
        plan = await PlanManager().get_plan_by_volume_for_display(
            gb=package_size / (1024**3),
            panel_code=panel_code,
        )
    except Exception as exc:
        logger.warning(
            "support snapshot: fair-usage lookup failed for service %s: %s",
            getattr(service, "code", "?"),
            exc,
        )
        return False
    return bool(plan and getattr(plan, "plan_type", None) in FAIR_USAGE_PLAN_TYPES)


def build_service_card(service: Any, panel: Any | None = None, *, now: datetime | None = None) -> ServiceSnapshot:
    """Database-only snapshot: enough for a picker row, with no panel call."""
    now = _now(now)
    expiration_time = _as_int(getattr(service, "expiration_time", None))
    if not expiration_time:
        state = STATE_ACTIVE
    else:
        state = STATE_EXPIRED if expiration_time <= int(now.timestamp()) else STATE_ACTIVE
    expire_at = datetime.fromtimestamp(expiration_time, tz=UTC) if expiration_time else None
    return ServiceSnapshot(
        code=int(getattr(service, "code", 0) or 0),
        config_name=str(getattr(service, "username", "") or ""),
        panel_name=str(getattr(panel, "name", "") or "پنل نامشخص"),
        panel_code=_as_int(getattr(service, "in_panel", None)),
        owner_id=_as_int(getattr(service, "id", None)),
        is_test=getattr(service, "is_test", False) is True,
        state=state,
        panel_available=False,
        expiration_time=expiration_time,
        expire_at=expire_at,
        expiring_soon=state == STATE_ACTIVE and _expiring_soon(expire_at, now),
    )


def build_service_snapshot(
    service: Any,
    panel: Any | None,
    panel_user: Any | None = None,
    *,
    now: datetime | None = None,
    can_renew: bool = False,
    can_buy_volume: bool = False,
    panel_error: str | None = None,
) -> ServiceSnapshot:
    """Snapshot from a panel user (or from the bot database when it is missing)."""
    now = _now(now)
    expiration_time = _as_int(getattr(service, "expiration_time", None))
    base = ServiceSnapshot(
        code=int(getattr(service, "code", 0) or 0),
        config_name=str(getattr(service, "username", "") or ""),
        panel_name=str(getattr(panel, "name", "") or "پنل نامشخص"),
        panel_code=_as_int(getattr(service, "in_panel", None)),
        owner_id=_as_int(getattr(service, "id", None)),
        is_test=getattr(service, "is_test", False) is True,
        state=STATE_UNKNOWN,
        panel_available=False,
        panel_error=panel_error,
        expiration_time=expiration_time,
        expire_at=datetime.fromtimestamp(expiration_time, tz=UTC) if expiration_time else None,
        can_renew=can_renew,
        can_buy_volume=can_buy_volume,
    )
    if panel_user is None:
        return base

    expire_at = coerce_datetime(getattr(panel_user, "expire", None) or None)
    data_limit = _as_int(getattr(panel_user, "data_limit", None))
    used = _as_int(getattr(panel_user, "used_traffic", None))
    remaining = _remaining_bytes(data_limit, used)
    online_at = coerce_datetime(getattr(panel_user, "online_at", None))
    state = classify_state(
        panel_status=str(getattr(panel_user, "status", "") or ""),
        expire_at=expire_at,
        data_limit_bytes=data_limit,
        remaining_bytes=remaining,
        now=now,
    )
    return ServiceSnapshot(
        code=base.code,
        config_name=base.config_name,
        panel_name=base.panel_name,
        panel_code=base.panel_code,
        owner_id=base.owner_id,
        is_test=base.is_test,
        state=state,
        panel_available=True,
        panel_error=None,
        expiration_time=expiration_time,
        expire_at=expire_at,
        data_limit_bytes=data_limit,
        used_bytes=used,
        remaining_bytes=remaining,
        online_at=online_at,
        expiring_soon=state in (STATE_ACTIVE, STATE_ON_HOLD) and _expiring_soon(expire_at, now),
        low_volume=state in (STATE_ACTIVE, STATE_ON_HOLD) and _low_volume(data_limit, remaining),
        can_renew=can_renew,
        can_buy_volume=can_buy_volume,
    )


async def load_service_snapshot(
    service: Any,
    *,
    panel: Any | None = None,
    panels_by_code: dict[int, Any] | None = None,
    settings: Any | None = None,
    now: datetime | None = None,
    api_timeout: float = 8.0,
) -> ServiceSnapshot:
    """Read the panel user and build a snapshot. Never raises for a panel problem."""
    if panel is None:
        panel_code = _as_int(getattr(service, "in_panel", None))
        panel = (panels_by_code or {}).get(panel_code) if panel_code is not None else None
        if panel is None and panel_code is not None:
            panel = await PanelsManager().get_panel_by_code(code=panel_code)
    if settings is None:
        settings = await SettingsManager().get_settings()

    can_renew, can_buy_volume = default_action_flags(service, panel, settings)
    if can_buy_volume and await service_uses_fair_usage_plan(service):
        can_buy_volume = False

    panel_user = None
    panel_error = None
    if panel is None:
        panel_error = PANEL_ERROR_MISSING
    else:
        try:
            panel_user = await PasarguardAPI(panel.base_url, timeout=api_timeout).get_user_by_id(
                user_id=require_panel_userid(service),
                token=panel.cookie,
            )
        except ValueError:
            panel_error = PANEL_ERROR_USERID_MISSING
            logger.warning("support snapshot: service %s has no panel user id", getattr(service, "code", "?"))
        except HTTPStatusError as exc:
            panel_error = PANEL_ERROR_NOT_IN_PANEL if exc.response.status_code == 404 else PANEL_ERROR_UNREACHABLE
            logger.warning(
                "support snapshot: panel %s answered %s for service %s",
                getattr(panel, "code", "?"),
                exc.response.status_code,
                getattr(service, "code", "?"),
            )
        except Exception as exc:
            panel_error = PANEL_ERROR_UNREACHABLE
            logger.warning(
                "support snapshot: panel %s unavailable for service %s: %s",
                getattr(panel, "code", "?"),
                getattr(service, "code", "?"),
                exc,
            )

    return build_service_snapshot(
        service,
        panel,
        panel_user,
        now=now,
        can_renew=can_renew,
        can_buy_volume=can_buy_volume,
        panel_error=panel_error,
    )


async def load_services_overview(
    user_id: int,
    *,
    now: datetime | None = None,
    panels_by_code: dict[int, Any] | None = None,
) -> ServicesOverview:
    """Every service of one user, from the bot database only."""
    services = await ServiceCRUD().get_services_reverse(user_id=user_id)
    if panels_by_code is None:
        panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
    return ServicesOverview(
        tuple(
            build_service_card(service, panels_by_code.get(_as_int(getattr(service, "in_panel", None))), now=now)
            for service in services
        )
    )


async def load_service_states(
    services: list[Any],
    *,
    panels_by_code: dict[int, Any] | None = None,
    now: datetime | None = None,
    api_timeout: float = 3.0,
) -> list[ServiceSnapshot]:
    """Read live states once per panel, preserving service order and database fallbacks."""
    now = _now(now)
    if panels_by_code is None:
        panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
    cards = [
        build_service_card(service, panels_by_code.get(_as_int(getattr(service, "in_panel", None))), now=now)
        for service in services
    ]
    by_panel: dict[int, list[tuple[int, int]]] = {}
    for index, service in enumerate(services):
        panel_code = _as_int(getattr(service, "in_panel", None))
        user_id = _as_int(getattr(service, "panel_userid", None))
        if panel_code in panels_by_code and user_id is not None:
            by_panel.setdefault(panel_code, []).append((index, user_id))

    async def _states(panel_code: int, entries: list[tuple[int, int]]) -> None:
        panel = panels_by_code[panel_code]
        ids = list(dict.fromkeys(user_id for _, user_id in entries))
        try:
            response = await PasarguardAPI(panel.base_url, timeout=api_timeout).get_users(
                token=panel.cookie,
                ids=ids,
                limit=len(ids),
            )
        except Exception as exc:
            logger.debug("support picker: live states unavailable for panel %s: %s", panel_code, exc)
            return
        users = {user.id: user for user in response.users}
        for index, user_id in entries:
            if (panel_user := users.get(user_id)) is not None:
                cards[index] = build_service_snapshot(services[index], panel, panel_user, now=now)

    await asyncio.gather(*(_states(panel_code, entries) for panel_code, entries in by_panel.items()))
    return cards

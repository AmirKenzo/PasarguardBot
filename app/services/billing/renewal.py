"""Volume calculation for service renewal (panel-level modes)."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from pasarguard import PasarguardAPI, UserModify
from pasarguard.enums import UserDataLimitResetStrategy

from app.db.crud.services import ServiceCRUD
from app.db.crud.user import debit_Money_if_sufficient, update_Money
from app.logger import get_logger
from app.services.panels.settings import panel_renew_volume_remaining_mode
from app.utils.formatting.conversions import gigabytes_to_bytes, plan_duration_to_expire

logger = get_logger(__name__)


class PaidRenewalError(Exception):
    """Balance deduction or renewal pre-check failed."""


def is_fair_usage_plan(plan: Any) -> bool:
    return bool(plan and getattr(plan, "plan_type", None) in ("fair_usage", "fair"))


def panel_renew_uses_remaining_volume(panel: Any) -> bool:
    """When True, volume renewal = remaining + purchased and used traffic is reset."""
    return panel_renew_volume_remaining_mode(panel)


def get_remaining_volume_bytes(panel_user: Any) -> int:
    data_limit = int(getattr(panel_user, "data_limit", 0) or 0)
    used_traffic = int(getattr(panel_user, "used_traffic", 0) or 0)
    return max(data_limit - used_traffic, 0)


def compute_renewal_data_limit_bytes(panel: Any, panel_user: Any, plan: Any) -> tuple[int, bool]:
    """
    Compute new data_limit (bytes) and whether used traffic should be reset.

    Returns:
        (new_data_limit_bytes, reset_used_traffic)
    """
    gig = float(plan.storage)
    purchased_bytes = gigabytes_to_bytes(gig)

    if is_fair_usage_plan(plan):
        return purchased_bytes, True

    current_limit = int(getattr(panel_user, "data_limit", 0) or 0)
    if panel_renew_uses_remaining_volume(panel):
        return get_remaining_volume_bytes(panel_user) + purchased_bytes, True

    return current_limit + purchased_bytes, False


def preview_remaining_after_renewal(panel: Any, panel_user: Any, plan: Any) -> tuple[int, int]:
    """Return (current_remaining_bytes, remaining_after_renewal_bytes) for confirm UI."""
    current_remaining = get_remaining_volume_bytes(panel_user)
    new_limit, _ = compute_renewal_data_limit_bytes(panel, panel_user, plan)
    if is_fair_usage_plan(plan) or panel_renew_uses_remaining_volume(panel):
        new_remaining = new_limit
    else:
        new_remaining = current_remaining + gigabytes_to_bytes(float(plan.storage))
    return current_remaining, new_remaining


def require_panel_userid(service: Any) -> int:
    panel_userid = getattr(service, "panel_userid", None)
    if panel_userid is None:
        raise ValueError("آیدی کاربر پنل ثبت نشده است. ابتدا سینک آیدی کاربران را از تنظیمات پنل انجام دهید.")
    return int(panel_userid)


async def fetch_panel_user(api: PasarguardAPI, panel: Any, service: Any) -> Any:
    return await api.get_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)


def _renewal_reset_strategy(plan: Any) -> UserDataLimitResetStrategy:
    reset_strategy = UserDataLimitResetStrategy.NO_RESET
    if (
        plan
        and hasattr(plan, "plan_type")
        and hasattr(plan, "data_limit_reset_strategy")
        and plan.plan_type in ("fair_usage", "fair")
        and plan.data_limit_reset_strategy
    ):
        with suppress(ValueError, TypeError):
            reset_strategy = UserDataLimitResetStrategy(plan.data_limit_reset_strategy)
    return reset_strategy


async def apply_panel_user_renewal(
    panel: Any,
    panel_userid: int,
    panel_user: Any,
    plan: Any,
    *,
    api: PasarguardAPI | None = None,
) -> int:
    """Apply renewal on Pasarguard panel. Returns new data_limit in bytes."""
    if api is None:
        api = PasarguardAPI(panel.base_url)

    new_hajm, reset_usage = compute_renewal_data_limit_bytes(panel, panel_user, plan)
    reset_strategy = _renewal_reset_strategy(plan)
    ip_limit = getattr(plan, "ip_limit", 0) or 0

    # Reset usage before lowering/setting data_limit — otherwise used_traffic can exceed
    # the new limit briefly and Pasarguard fires a volume-exhausted webhook.
    if reset_usage:
        await api.reset_user_data_usage_by_id(user_id=panel_userid, token=panel.cookie)

    await api.modify_user_by_id(
        user_id=panel_userid,
        user=UserModify(
            data_limit=new_hajm,
            expire=plan_duration_to_expire(plan.duration),
            data_limit_reset_strategy=reset_strategy,
            hwid_limit=ip_limit if ip_limit > 0 else 0,
        ),
        token=panel.cookie,
    )

    return new_hajm


async def execute_paid_service_renewal(
    service: Any,
    panel: Any,
    plan: Any,
    *,
    price: int,
    panel_user: Any,
) -> tuple[int, int]:
    """
    Deduct wallet balance, renew on panel, update service row.
    Refunds balance if panel/DB update fails after deduction.
    Returns (new_data_limit_bytes, new_balance).
    """
    user_id = int(service.id)
    service_crud = ServiceCRUD()
    api = PasarguardAPI(panel.base_url)
    panel_userid = require_panel_userid(service)

    new_balance = await debit_Money_if_sufficient(user_id=user_id, amount=int(price))
    if new_balance is None:
        raise PaidRenewalError("موجودی کیف پول کافی نیست یا کاربر برای کسر موجودی یافت نشد")

    service_updates: dict[str, Any] = {
        "warning": 0,
        "warning_time": 0,
        "low_volume_notified": False,
        "expire_notified": False,
        "ip_limit": getattr(plan, "ip_limit", 0) or 0,
    }

    try:
        new_hajm = await apply_panel_user_renewal(panel, panel_userid, panel_user, plan, api=api)
        await service_crud.update_service(
            code=service.code,
            package_size=int(new_hajm),
            expiration_time=plan_duration_to_expire(plan.duration),
            **service_updates,
        )
        return new_hajm, int(new_balance)
    except Exception as exc:
        refund_balance = await update_Money(user_id=user_id, Money=int(price))
        logger.warning(
            "Paid renewal rolled back balance service=%s user=%s refund_balance=%s error=%s",
            getattr(service, "code", None),
            user_id,
            refund_balance,
            exc,
        )
        raise

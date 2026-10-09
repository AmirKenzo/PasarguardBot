"""Reseller accounts and their admin actions, plus reseller plans.

Every action goes through ``app.services.reseller`` so the web panel follows the same rules
(panel sync, wallet checks, event history) as the bot.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request

from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_events import ResellerEventCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.models.reseller_events import ResellerEvent
from app.db.models.reseller_plans import PRICING_MODES
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest, page_meta
from app.models.panel.resellers import (
    RESELLER_STATUSES,
    PanelResellerCodeRequest,
    PanelResellerDeleteRequest,
    PanelResellerDetailRequest,
    PanelResellerDetailResponse,
    PanelResellerEventRow,
    PanelResellerExtendRequest,
    PanelResellerLive,
    PanelResellerMaxUsersRequest,
    PanelResellerPasswordResponse,
    PanelResellerPlanBrief,
    PanelResellerPlanDeleteRequest,
    PanelResellerPlanRow,
    PanelResellerPlanSaveRequest,
    PanelResellerPlansResponse,
    PanelResellerRenewRequest,
    PanelResellerRow,
    PanelResellerSnapshotRow,
    PanelResellersRequest,
    PanelResellersResponse,
    PanelResellerUpdateRequest,
    PanelResellerUsageCapRequest,
)
from app.models.panel.services import PanelPanelOption
from app.panel import audit, mutations, queries
from app.panel.forms import parse_icon, parse_style
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.reseller.accounts import (
    ADMIN_LOCKED_STATUS,
    PAYG_MODES,
    delete_account,
    extend_account_by_admin,
    load_account_live_info,
    pause_account_by_admin,
    reset_password,
    resume_account_by_admin,
    reveal_password,
    set_max_users_by_admin,
)
from app.services.reseller.plan_changes import LIVE_RATE_MODES, notify_plan_rate_change
from app.services.reseller.runway import estimate_runway
from app.services.reseller.usage_cap import set_reseller_usage_cap
from app.telegram.state.lock import acquire_user_lock, release_user_lock
from app.utils.formatting.conversions import gigabytes_to_bytes

log = get_logger(__name__)

router = APIRouter()

GB = 1024**3
ADMIN_ROLE = "ادمین"
NOT_FOUND = "حساب نمایندگی با این کد پیدا نشد."

# Admin actions on one account; the detail endpoint lists which ones currently apply.
ADMIN_ACTION_PAUSE = "pause"
ADMIN_ACTION_RESUME = "resume"
ADMIN_ACTION_PASSWORD = "password"
ADMIN_ACTION_RENEW = "renew"
ADMIN_ACTION_EXTEND = "extend"
ADMIN_ACTION_USAGE_CAP = "usage_cap"
ADMIN_ACTION_MAX_USERS = "max_users"
ADMIN_ACTION_DELETE = "delete"

# Rate-change notices run after the response so a large plan never stalls the request.
_background_tasks: set[asyncio.Task] = set()


def reseller_row(account, panels: dict[int, str]) -> PanelResellerRow:
    return PanelResellerRow(
        code=int(account.code),
        telegram_id=account.telegram_id,
        username=account.username,
        panel_code=account.panel_code,
        panel=panels.get(int(account.panel_code or 0)),
        panel_admin_id=account.panel_admin_id,
        plan_id=account.plan_id,
        pricing_mode=account.pricing_mode,
        purchased_volume=account.purchased_volume,
        data_limit=account.data_limit,
        usage_cap_bytes=account.usage_cap_bytes,
        max_users=account.max_users,
        createtime=account.createtime,
        expiration_time=account.expiration_time,
        status=account.status,
    )


def snapshot_row(snapshot, account=None) -> PanelResellerSnapshotRow:
    return PanelResellerSnapshotRow(
        id=int(snapshot.id),
        account_code=int(snapshot.account_code) if snapshot.account_code is not None else None,
        username=account.username if account is not None else None,
        telegram_id=account.telegram_id if account is not None else None,
        kind="hourly" if snapshot.billed_minutes is not None else "usage",
        used_traffic=int(snapshot.used_traffic or 0),
        billed_amount=int(snapshot.billed_amount or 0),
        billed_minutes=snapshot.billed_minutes,
        snapshot_at=snapshot.snapshot_at,
    )


def event_row(event: ResellerEvent) -> PanelResellerEventRow:
    return PanelResellerEventRow(
        id=int(event.id),
        kind=event.kind,
        title=event.title,
        account_code=event.account_code,
        telegram_id=event.telegram_id,
        actor_id=event.actor_id,
        actor_role=event.actor_role,
        data=ResellerEventCRUD.load_data(event),
        created_at=int(event.created_at),
    )


def plan_brief(plan) -> PanelResellerPlanBrief:
    name = (plan.display_button_text or "").strip().split("\n", 1)[0][:40] or None
    rate = float(plan.price or 0) if plan.pricing_mode == "fixed" else float(plan.unit_price or 0)
    return PanelResellerPlanBrief(id=int(plan.id), pricing_mode=plan.pricing_mode, name=name, rate=rate)


def admin_actions(account) -> list[str]:
    actions = [ADMIN_ACTION_PASSWORD, ADMIN_ACTION_MAX_USERS, ADMIN_ACTION_DELETE]
    if account.status in ("paused", ADMIN_LOCKED_STATUS):
        actions.append(ADMIN_ACTION_RESUME)
    elif account.status != "expired":
        actions.append(ADMIN_ACTION_PAUSE)
    if account.pricing_mode == "fixed":
        actions.append(ADMIN_ACTION_RENEW)
    if account.expiration_time:
        actions.append(ADMIN_ACTION_EXTEND)
    if account.pricing_mode == "usage":
        actions.append(ADMIN_ACTION_USAGE_CAP)
    return actions


async def _record(actor: PanelActor, action: str, code: int, detail: dict[str, Any] | None = None) -> None:
    await audit.record(
        actor_id=actor.user_id,
        actor_username=actor.username,
        action=action,
        target_type="reseller",
        target_id=code,
        detail=detail,
        ip=actor.ip,
    )


def _result(ok: bool, message: str) -> ActionResponse:
    return ActionResponse(message=message) if ok else ActionResponse(ok=False, error=message)


# --------------------------------------------------------------------------- #
#  Accounts                                                                     #
# --------------------------------------------------------------------------- #


@router.post("/panel/resellers", response_model=PanelResellersResponse)
async def list_resellers(payload: PanelResellersRequest, request: Request) -> PanelResellersResponse:
    async def handle(_: PanelActor) -> PanelResellersResponse:
        status = payload.status if payload.status in RESELLER_STATUSES else ""
        mode = payload.pricing_mode if payload.pricing_mode in PRICING_MODES else ""
        (rows, total), panels = await asyncio.gather(
            queries.list_resellers(
                status=status,
                q=payload.q.strip(),
                panel_code=payload.panel_code,
                pricing_mode=mode,
                page=payload.page,
                per_page=payload.limit,
            ),
            queries.panel_names(),
        )
        return PanelResellersResponse(
            resellers=[reseller_row(account, panels) for account in rows],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
            pricing_modes=list(PRICING_MODES),
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelResellersResponse, handle)


@router.post("/panel/resellers/detail", response_model=PanelResellerDetailResponse)
async def reseller_detail(payload: PanelResellerDetailRequest, request: Request) -> PanelResellerDetailResponse:
    async def handle(_: PanelActor) -> PanelResellerDetailResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return PanelResellerDetailResponse(ok=False, error=NOT_FOUND)

        panels, snapshots, (events, _total) = await asyncio.gather(
            queries.panel_names(),
            queries.reseller_snapshots(payload.code),
            ResellerEventCRUD().list_events(account_code=payload.code, limit=20),
        )
        response = PanelResellerDetailResponse(
            reseller=reseller_row(account, panels),
            actions=admin_actions(account),
            snapshots=[snapshot_row(snapshot, account) for snapshot in snapshots],
            events=[event_row(event) for event in events],
        )

        plan = None
        try:
            info = await load_account_live_info(account)
            plan = info.plan
            response.live = PanelResellerLive(
                used_traffic=info.used_traffic,
                data_limit=info.data_limit,
                total_users=info.total_users,
                admin_status=info.admin_status,
                login_url=info.login_url,
            )
            response.balance = info.balance
            response.billed_total = info.billed_total
            response.grace_days_left = info.grace_days_left
        except Exception as exc:
            log.warning("reseller detail live info failed code=%s: %s", account.code, exc)
            response.live_error = "اطلاعات زنده از پنل دریافت نشد."
            plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None

        if plan is not None:
            response.plan = plan_brief(plan)

        if account.pricing_mode in PAYG_MODES:
            if response.balance is None:
                response.balance = (await queries.user_balances([account.telegram_id])).get(account.telegram_id, 0)
            user_accounts = await ResellerAccountCRUD().get_accounts_by_user(account.telegram_id)
            response.runway_hours = (await estimate_runway(response.balance, user_accounts)).hours_left

        if account.pricing_mode == "fixed":
            response.renew_plans = [
                plan_brief(item)
                for item in await ResellerPlanManager().get_all_plans(panel_code=account.panel_code, enabled_only=True)
                if item.pricing_mode == "fixed"
            ]
        return response

    return await guard.run(payload, request, PanelResellerDetailResponse, handle)


@router.post("/panel/resellers/update", response_model=ActionResponse)
async def update_reseller(payload: PanelResellerUpdateRequest, request: Request) -> ActionResponse:
    """All-in-one edit kept for older clients; each change runs through the same service as its own action."""

    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)

        messages: list[str] = []

        async def step(result: tuple[bool, str]) -> str | None:
            nonlocal account
            ok, message = result
            if not ok:
                return message
            messages.append(message)
            account = await queries.get_reseller(payload.code) or account
            return None

        if payload.status and payload.status != account.status:
            if payload.status == "active":
                if account.status == "expired":
                    return ActionResponse(ok=False, error="برای فعال‌سازی نمایندگی منقضی، آن را تمدید کنید.")
                error = await step(await resume_account_by_admin(account, actor_id=actor.user_id))
            elif payload.status in ("paused", "suspended", ADMIN_LOCKED_STATUS):
                error = await step(await pause_account_by_admin(account, actor_id=actor.user_id))
            else:
                error = "این وضعیت را نمی‌توان دستی تنظیم کرد."
            if error:
                return ActionResponse(ok=False, error=error)

        if account.pricing_mode == "usage":
            wanted_cap = gigabytes_to_bytes(payload.usage_cap_gb) if payload.usage_cap_gb else 0
            current_cap = int(account.usage_cap_bytes or 0)
            # Older forms round the cap to 0.01 GB; don't treat that rounding as an edit.
            if bool(wanted_cap) != bool(current_cap) or abs(wanted_cap - current_cap) >= GB // 100:
                error = await step(
                    await set_reseller_usage_cap(
                        account, gigabytes=payload.usage_cap_gb, actor_id=actor.user_id, actor_role=ADMIN_ROLE
                    )
                )
                if error:
                    return ActionResponse(ok=False, error=error)

        if payload.max_users != int(account.max_users or 0):
            error = await step(
                await set_max_users_by_admin(account, max_users=payload.max_users, actor_id=actor.user_id)
            )
            if error:
                return ActionResponse(ok=False, error=error)

        if payload.extend_days:
            error = await step(await extend_account_by_admin(account, days=payload.extend_days, actor_id=actor.user_id))
            if error:
                return ActionResponse(ok=False, error=error)

        if not messages:
            return ActionResponse(message="تغییری برای ذخیره وجود نداشت.")
        await _record(
            actor, "reseller_update", payload.code, payload.model_dump(exclude={"init_data", "session_token"})
        )
        return ActionResponse(message=" ".join(messages))

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/pause", response_model=ActionResponse)
async def pause_reseller(payload: PanelResellerCodeRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await pause_account_by_admin(account, actor_id=actor.user_id)
        if ok:
            await _record(actor, "reseller_pause", payload.code)
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/resume", response_model=ActionResponse)
async def resume_reseller(payload: PanelResellerCodeRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await resume_account_by_admin(account, actor_id=actor.user_id)
        if ok:
            await _record(actor, "reseller_resume", payload.code)
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/password", response_model=PanelResellerPasswordResponse)
async def reveal_reseller_password(
    payload: PanelResellerCodeRequest, request: Request
) -> PanelResellerPasswordResponse:
    async def handle(actor: PanelActor) -> PanelResellerPasswordResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return PanelResellerPasswordResponse(ok=False, error=NOT_FOUND)
        try:
            password = reveal_password(account)
        except Exception as exc:
            log.error("reseller password decrypt failed code=%s: %s", account.code, exc)
            return PanelResellerPasswordResponse(ok=False, error="رمز ذخیره‌شده قابل خواندن نیست؛ رمز جدید بسازید.")
        await _record(actor, "reseller_password_view", payload.code)
        return PanelResellerPasswordResponse(password=password)

    return await guard.run(payload, request, PanelResellerPasswordResponse, handle)


@router.post("/panel/resellers/password/reset", response_model=PanelResellerPasswordResponse)
async def reset_reseller_password(payload: PanelResellerCodeRequest, request: Request) -> PanelResellerPasswordResponse:
    async def handle(actor: PanelActor) -> PanelResellerPasswordResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return PanelResellerPasswordResponse(ok=False, error=NOT_FOUND)
        ok, message, password = await reset_password(account, actor_id=actor.user_id, actor_role=ADMIN_ROLE)
        if not ok:
            return PanelResellerPasswordResponse(ok=False, error=message)
        await _record(actor, "reseller_password_reset", payload.code)
        return PanelResellerPasswordResponse(message=message, password=password)

    return await guard.run(payload, request, PanelResellerPasswordResponse, handle)


@router.post("/panel/resellers/renew", response_model=ActionResponse)
async def renew_reseller(payload: PanelResellerRenewRequest, request: Request) -> ActionResponse:
    """Renew a fixed account with a plan; the price is taken from the reseller's wallet, as in the bot."""

    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        if not await acquire_user_lock(account.telegram_id, "reseller_renew", ttl=30):
            return ActionResponse(ok=False, error="یک عملیات دیگر روی کیف پول این کاربر در جریان است.")
        try:
            ok, message = await renew_reseller_account(
                account.code,
                payload.plan_id,
                account.telegram_id,
                actor_id=actor.user_id,
                actor_role=ADMIN_ROLE,
            )
        finally:
            await release_user_lock(account.telegram_id, "reseller_renew")
        if ok:
            await _record(actor, "reseller_renew", payload.code, {"plan_id": payload.plan_id})
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/extend", response_model=ActionResponse)
async def extend_reseller(payload: PanelResellerExtendRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await extend_account_by_admin(account, days=payload.days, actor_id=actor.user_id)
        if ok:
            await _record(actor, "reseller_extend", payload.code, {"days": payload.days})
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/usage-cap", response_model=ActionResponse)
async def set_reseller_cap(payload: PanelResellerUsageCapRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await set_reseller_usage_cap(
            account, gigabytes=payload.usage_cap_gb, actor_id=actor.user_id, actor_role=ADMIN_ROLE
        )
        if ok:
            await _record(actor, "reseller_usage_cap", payload.code, {"usage_cap_gb": payload.usage_cap_gb})
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/max-users", response_model=ActionResponse)
async def set_reseller_max_users(payload: PanelResellerMaxUsersRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await set_max_users_by_admin(account, max_users=payload.max_users, actor_id=actor.user_id)
        if ok:
            await _record(actor, "reseller_max_users", payload.code, {"max_users": payload.max_users})
        return _result(ok, message)

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/resellers/delete", response_model=ActionResponse)
async def delete_reseller(payload: PanelResellerDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        account = await queries.get_reseller(payload.code)
        if account is None:
            return ActionResponse(ok=False, error=NOT_FOUND)
        ok, message = await delete_account(account, actor_id=actor.user_id, actor_role=ADMIN_ROLE)
        if ok:
            await _record(actor, "reseller_delete", payload.code, {"username": account.username})
        return _result(ok, message.replace("`", ""))

    return await guard.run(payload, request, ActionResponse, handle)


# --------------------------------------------------------------------------- #
#  Reseller plans                                                               #
# --------------------------------------------------------------------------- #


@router.post("/panel/reseller-plans", response_model=PanelResellerPlansResponse)
async def list_reseller_plans(payload: PanelRequest, request: Request) -> PanelResellerPlansResponse:
    async def handle(_: PanelActor) -> PanelResellerPlansResponse:
        plans, panels, linked = await asyncio.gather(
            queries.list_reseller_plans(),
            queries.panel_names(),
            queries.reseller_plan_link_counts(),
        )
        return PanelResellerPlansResponse(
            plans=[
                PanelResellerPlanRow(
                    id=int(plan.id),
                    panel_code=int(plan.panel_code),
                    panel=panels.get(int(plan.panel_code)),
                    pricing_mode=plan.pricing_mode,
                    price=float(plan.price or 0),
                    unit_price=float(plan.unit_price or 0),
                    min_volume=float(plan.min_volume or 0),
                    max_volume=float(plan.max_volume or 0),
                    volume_step=float(plan.volume_step or 1),
                    data_limit_gb=round(int(plan.data_limit or 0) / GB, 2),
                    max_users=int(plan.max_users or 0),
                    duration=int(plan.duration or 0),
                    role_id=int(plan.role_id or 0),
                    role_name=plan.role_name,
                    enable=bool(plan.enable),
                    display_button_text=plan.display_button_text,
                    button_style=plan.button_style,
                    button_icon=plan.button_icon,
                    linked_accounts=linked.get(int(plan.id), 0),
                )
                for plan in plans
            ],
            panels=[PanelPanelOption(code=code, name=name) for code, name in panels.items()],
            pricing_modes=list(PRICING_MODES),
        )

    return await guard.run(payload, request, PanelResellerPlansResponse, handle)


def _plan_price_error(payload: PanelResellerPlanSaveRequest) -> str | None:
    if payload.pricing_mode not in PRICING_MODES:
        return "مدل قیمت‌گذاری معتبر نیست."
    if payload.pricing_mode == "fixed" and payload.price <= 0:
        return "قیمت پلن ثابت باید بیشتر از صفر باشد."
    if payload.pricing_mode != "fixed" and payload.unit_price <= 0:
        return "قیمت واحد باید بیشتر از صفر باشد."
    if payload.max_volume and payload.max_volume < payload.min_volume:
        return "حداکثر حجم نمی‌تواند از حداقل کمتر باشد."
    return None


def _schedule_rate_notice(plan, old_rate: float, new_rate: float, actor_id: int) -> None:
    async def run() -> None:
        try:
            await notify_plan_rate_change(plan, old_rate=old_rate, new_rate=new_rate, actor_id=actor_id)
        except Exception as exc:
            log.error("plan rate notice failed plan=%s: %s", plan.id, exc, exc_info=True)

    task = asyncio.create_task(run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.post("/panel/reseller-plans/save", response_model=ActionResponse)
async def save_reseller_plan(payload: PanelResellerPlanSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        panels = await queries.panel_names()
        if payload.panel_code not in panels:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        error = _plan_price_error(payload)
        if error:
            return ActionResponse(ok=False, error=error)
        try:
            icon = parse_icon(payload.button_icon)
        except ValueError:
            return ActionResponse(ok=False, error="آیدی ایموجی معتبر نیست.")

        existing = None
        if payload.plan_id is not None:
            existing = await queries.get_reseller_plan(payload.plan_id)
            if existing is None:
                return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")
            linked = await ResellerAccountCRUD().count_accounts_by_plan(payload.plan_id)
            if linked and (
                payload.pricing_mode != existing.pricing_mode or payload.panel_code != int(existing.panel_code)
            ):
                return ActionResponse(
                    ok=False,
                    error=f"این پلن به {linked} نمایندگی متصل است؛ پنل و مدل قیمت‌گذاری آن قابل تغییر نیست.",
                )

        values = {
            "panel_code": payload.panel_code,
            "pricing_mode": payload.pricing_mode,
            "price": payload.price,
            "unit_price": payload.unit_price,
            "min_volume": payload.min_volume,
            "max_volume": payload.max_volume,
            "volume_step": payload.volume_step,
            "max_users": payload.max_users,
            "duration": payload.duration,
            "role_id": payload.role_id,
            "role_name": payload.role_name.strip() or None,
            "enable": payload.enable,
            "display_button_text": payload.display_button_text.strip() or None,
            "button_style": parse_style(payload.button_style),
            "button_icon": icon,
        }
        if payload.data_limit_gb is not None:
            values["data_limit"] = int(gigabytes_to_bytes(payload.data_limit_gb)) if payload.data_limit_gb else 0

        await mutations.upsert_reseller_plan(actor, payload.plan_id, values)

        if (
            existing is not None
            and payload.notify_resellers
            and existing.pricing_mode in LIVE_RATE_MODES
            and int(existing.unit_price or 0) != int(payload.unit_price)
        ):
            _schedule_rate_notice(existing, float(existing.unit_price or 0), float(payload.unit_price), actor.user_id)
        return ActionResponse(message="پلن نمایندگی ذخیره شد." if payload.plan_id else "پلن نمایندگی اضافه شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/reseller-plans/delete", response_model=ActionResponse)
async def delete_reseller_plan(payload: PanelResellerPlanDeleteRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        # An account without its plan is billed at rate 0, so linked plans can only be disabled.
        linked = await ResellerAccountCRUD().count_accounts_by_plan(payload.plan_id)
        if linked:
            return ActionResponse(
                ok=False, error=f"این پلن روی {linked} نمایندگی استفاده شده و قابل حذف نیست؛ می‌توانید غیرفعالش کنید."
            )
        ok = await mutations.delete_reseller_plan(actor, payload.plan_id)
        if not ok:
            return ActionResponse(ok=False, error="پلنی با این شناسه پیدا نشد.")
        return ActionResponse(message="پلن نمایندگی حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)

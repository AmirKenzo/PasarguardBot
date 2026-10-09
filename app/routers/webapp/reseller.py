"""Reseller purchase and self-service management for the web app.

Mirrors the bot's reseller flow (app/telegram/user/reseller): the same services, the same
per-panel button toggles (``account_actions``) and server-side prices — a hidden button is
also a refused request here.
"""

from __future__ import annotations

import random

from fastapi import APIRouter

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_events import ResellerEventCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.models.webapp.common import WebAppAuthRequest
from app.models.webapp.reseller import (
    ResellerAccountItem,
    ResellerEventItem,
    ResellerPanelItem,
    ResellerPlanItem,
    ResellerRenewPlanItem,
    ResellerUsageRow,
    WebAppResellerAccountResponse,
    WebAppResellerAccountsResponse,
    WebAppResellerActionResponse,
    WebAppResellerBuyConfirmResponse,
    WebAppResellerBuyOptionsResponse,
    WebAppResellerBuyPreviewResponse,
    WebAppResellerBuyRequest,
    WebAppResellerCapacityPreviewResponse,
    WebAppResellerCapacityRequest,
    WebAppResellerCodeRequest,
    WebAppResellerEventsResponse,
    WebAppResellerPageRequest,
    WebAppResellerPasswordResponse,
    WebAppResellerRenewPreviewResponse,
    WebAppResellerRenewRequest,
    WebAppResellerUsageCapRequest,
    WebAppResellerUsageResponse,
    WebAppResellerUsernameRequest,
    WebAppResellerUsernameResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    requires_volume_input,
    requires_wallet_for_purchase,
)
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.panels.admins import admin_username_exists
from app.services.panels.settings import panel_reseller_capacity_settings, panel_reseller_sale_enabled
from app.services.reseller.accounts import (
    ACTION_BUY_CAPACITY,
    ACTION_CHANGE_PASSWORD,
    ACTION_CREDENTIALS,
    ACTION_DELETE,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_RESUME,
    ACTION_USAGE_CAP,
    ACTION_USAGE_REPORT,
    PAYG_MODES,
    account_actions,
    delete_account,
    get_owned_account,
    is_admin_locked,
    load_account_live_info,
    pause_account,
    reset_password,
    resume_account,
    reveal_password,
)
from app.services.reseller.capacity import CAPACITY_PRESETS, calculate_capacity_price, increase_reseller_capacity
from app.services.reseller.ledger import describe_charges
from app.services.reseller.purchase import (
    apply_reseller_discount,
    purchase_reseller_account,
    quote_reseller_purchase,
    reseller_sale_open,
)
from app.services.reseller.runway import estimate_runway
from app.services.reseller.usage_cap import set_reseller_usage_cap
from app.services.webapp_purchase import is_valid_config_username
from app.telegram.state.lock import acquire_user_lock, release_user_lock

log = get_logger(__name__)
router = APIRouter()

GENERIC_ERROR = "اجرای این عملیات با خطا روبه‌رو شد. دوباره تلاش کنید."
USERNAME_RULE = "نام کاربری باید ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، عدد و زیرخط باشد."
LOCK_BUSY = "درخواست قبلی شما هنوز در حال انجام است."


class _Refused(Exception):
    """A request the rules turn down; its message goes back to the user."""


async def _user(request: WebAppAuthRequest) -> int:
    user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
    if not user_id:
        raise _Refused("ورود نامعتبر است.")
    return int(user_id)


async def _owned(code: int, user_id: int, action: str | None = None):
    """The caller's account and its panel; ``action`` must be one the bot would offer."""
    account = await get_owned_account(code, user_id)
    if account is None:
        raise _Refused("نمایندگی یافت نشد.")
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if action is not None and action not in account_actions(account, panel):
        if is_admin_locked(account):
            raise _Refused("این نمایندگی توسط ادمین غیرفعال شده است.")
        raise _Refused("این عملیات برای این نمایندگی فعال نیست.")
    return account, panel


async def _balance(user_id: int) -> int:
    user = await UserCRUD().read_user(user_id)
    return int(getattr(user, "amount", 0) or 0) if user else 0


async def _run(response_model, call):
    """Turn refusals and auth errors into ``ok=False``; never leak internals for anything else."""
    try:
        return await call()
    except (_Refused, ValueError) as exc:
        return response_model(ok=False, error=str(exc))
    except Exception as exc:
        log.error("webapp reseller %s failed: %s", response_model.__name__, exc, exc_info=True)
        return response_model(ok=False, error=GENERIC_ERROR)


def _plan_name(plan) -> str | None:
    return (plan.display_button_text or "").strip().split("\n", 1)[0][:48] or None


def _plan_item(plan) -> ResellerPlanItem:
    return ResellerPlanItem(
        id=int(plan.id),
        pricing_mode=plan.pricing_mode,
        name=_plan_name(plan),
        price=int(plan.price or 0),
        unit_price=int(plan.unit_price or 0),
        min_volume=float(plan.min_volume or 0),
        max_volume=float(plan.max_volume or 0),
        volume_step=float(plan.volume_step or 1),
        data_limit_bytes=int(plan.data_limit or 0),
        max_users=int(plan.max_users or 0),
        duration_days=int(plan.duration or 0),
        needs_volume=requires_volume_input(plan),
        needs_wallet=requires_wallet_for_purchase(plan),
    )


def _renew_item(plan) -> ResellerRenewPlanItem:
    return ResellerRenewPlanItem(
        id=int(plan.id),
        name=_plan_name(plan),
        price=calculate_purchase_price(plan),
        data_limit_bytes=int(plan.data_limit or 0),
        duration_days=int(plan.duration or 0),
    )


def _account_item(account, panel_name: str | None) -> ResellerAccountItem:
    return ResellerAccountItem(
        code=int(account.code),
        username=account.username,
        panel_name=panel_name,
        pricing_mode=account.pricing_mode,
        status=account.status,
        expiration_timestamp=account.expiration_time,
        max_users=int(account.max_users or 0),
        created_timestamp=account.createtime,
    )


def _event_item(event) -> ResellerEventItem:
    return ResellerEventItem(
        id=int(event.id),
        kind=event.kind,
        title=event.title,
        data=ResellerEventCRUD.load_data(event),
        created_at=int(event.created_at),
    )


def _check_username(username: str) -> str:
    username = (username or "").strip()
    if not is_valid_config_username(username):
        raise _Refused(USERNAME_RULE)
    return username


async def _renew_plan(account, plan_id: int):
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not plan.enable or plan.pricing_mode != "fixed" or int(plan.panel_code) != int(account.panel_code):
        raise _Refused("پلن تمدید یافت نشد.")
    return plan


# --------------------------------------------------------------------------- #
#  Buy                                                                          #
# --------------------------------------------------------------------------- #


@router.post("/webapp/reseller/buy/options", response_model=WebAppResellerBuyOptionsResponse)
async def reseller_buy_options(request: WebAppAuthRequest) -> WebAppResellerBuyOptionsResponse:
    """Panels and plans on sale; ``enabled`` False hides reseller purchase entirely."""

    async def call() -> WebAppResellerBuyOptionsResponse:
        user_id = await _user(request)
        settings = await SettingsManager().get_settings()
        if not await reseller_sale_open(settings):
            return WebAppResellerBuyOptionsResponse(enabled=False)

        panels: list[ResellerPanelItem] = []
        for panel_code in await ResellerPlanManager().get_panels_with_plans(enabled_only=True):
            panel = await PanelsManager().get_panel_by_code(code=panel_code)
            if not panel or not panel_reseller_sale_enabled(panel):
                continue
            plans = await ResellerPlanManager().get_all_plans(panel_code=panel_code, enabled_only=True)
            if plans:
                panels.append(
                    ResellerPanelItem(code=int(panel.code), name=panel.name, plans=[_plan_item(p) for p in plans])
                )
        return WebAppResellerBuyOptionsResponse(
            enabled=bool(panels),
            min_wallet_balance=int(getattr(settings, "reseller_min_wallet_balance", 0) or 0),
            balance=await _balance(user_id),
            panels=panels,
        )

    return await _run(WebAppResellerBuyOptionsResponse, call)


@router.post("/webapp/reseller/buy/username", response_model=WebAppResellerUsernameResponse)
async def reseller_buy_username(request: WebAppResellerUsernameRequest) -> WebAppResellerUsernameResponse:
    """A random admin username that is free on the panel."""

    async def call() -> WebAppResellerUsernameResponse:
        await _user(request)
        panel = await PanelsManager().get_panel_by_code(code=request.panel_code)
        if not panel or not panel_reseller_sale_enabled(panel):
            raise _Refused("این پنل برای فروش نمایندگی فعال نیست.")
        for _ in range(6):
            username = f"res{random.randint(1000, 999999)}"
            if not await admin_username_exists(panel, username):
                return WebAppResellerUsernameResponse(username=username)
        raise _Refused("ساخت نام کاربری ناموفق بود؛ یک نام دلخواه وارد کنید.")

    return await _run(WebAppResellerUsernameResponse, call)


@router.post("/webapp/reseller/buy/preview", response_model=WebAppResellerBuyPreviewResponse)
async def reseller_buy_preview(request: WebAppResellerBuyRequest) -> WebAppResellerBuyPreviewResponse:
    async def call() -> WebAppResellerBuyPreviewResponse:
        user_id = await _user(request)
        username = _check_username(request.username)
        quote, error = await quote_reseller_purchase(
            user_id,
            panel_code=request.panel_code,
            plan_id=request.plan_id,
            volume=request.volume,
            discount_code=request.discount_code,
        )
        if error:
            raise _Refused(error)
        if await admin_username_exists(quote.panel, username):
            raise _Refused("این نام کاربری در پنل وجود دارد. نام دیگری انتخاب کنید.")
        balance = await _balance(user_id)
        price = quote.price.final_price
        return WebAppResellerBuyPreviewResponse(
            panel_name=quote.panel.name,
            plan=_plan_item(quote.plan),
            username=username,
            volume=quote.volume,
            base_price=quote.price.base_price,
            final_price=price,
            discount_percent=quote.price.discount_percent,
            balance=balance,
            balance_after=balance - price,
            can_pay=balance >= price and not quote.wallet_error,
            wallet_error=quote.wallet_error,
        )

    return await _run(WebAppResellerBuyPreviewResponse, call)


@router.post("/webapp/reseller/buy/confirm", response_model=WebAppResellerBuyConfirmResponse)
async def reseller_buy_confirm(request: WebAppResellerBuyRequest) -> WebAppResellerBuyConfirmResponse:
    """Re-validate and re-price on the server, then create the panel admin and debit the wallet."""

    async def call() -> WebAppResellerBuyConfirmResponse:
        user_id = await _user(request)
        username = _check_username(request.username)
        if not await acquire_user_lock(user_id, "reseller_buy", ttl=60):
            raise _Refused(LOCK_BUSY)
        try:
            quote, error = await quote_reseller_purchase(
                user_id,
                panel_code=request.panel_code,
                plan_id=request.plan_id,
                volume=request.volume,
                discount_code=request.discount_code,
            )
            if error:
                raise _Refused(error)
            if quote.wallet_error:
                raise _Refused(quote.wallet_error)
            outcome = await purchase_reseller_account(
                user_id,
                plan_id=quote.plan.id,
                panel_code=int(quote.panel.code),
                username=username,
                volume=quote.volume,
                amount=quote.price.final_price,
                discount_code=quote.price.discount_code,
            )
        finally:
            await release_user_lock(user_id, "reseller_buy")
        if not outcome.ok:
            raise _Refused(outcome.message)
        return WebAppResellerBuyConfirmResponse(
            account_code=outcome.account_code,
            panel_url=outcome.panel_url,
            username=username,
            password=outcome.password,
            amount_paid=quote.price.final_price,
            new_balance=outcome.new_balance,
        )

    return await _run(WebAppResellerBuyConfirmResponse, call)


# --------------------------------------------------------------------------- #
#  Accounts                                                                     #
# --------------------------------------------------------------------------- #


@router.post("/webapp/reseller/accounts", response_model=WebAppResellerAccountsResponse)
async def reseller_accounts(request: WebAppAuthRequest) -> WebAppResellerAccountsResponse:
    async def call() -> WebAppResellerAccountsResponse:
        user_id = await _user(request)
        accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
        names: dict[int, str] = {}
        for account in accounts:
            if account.panel_code not in names:
                panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
                names[account.panel_code] = panel.name if panel else str(account.panel_code)
        balance = await _balance(user_id)
        runway = await estimate_runway(balance, accounts)
        return WebAppResellerAccountsResponse(
            accounts=[
                _account_item(account, names.get(account.panel_code))
                for account in sorted(accounts, key=lambda a: a.createtime or 0, reverse=True)
            ],
            balance=balance,
            burn_per_hour=round(runway.burn_per_hour),
            runway_hours=round(runway.hours_left, 2) if runway.hours_left is not None else None,
            can_buy=await reseller_sale_open(),
        )

    return await _run(WebAppResellerAccountsResponse, call)


@router.post("/webapp/reseller/account", response_model=WebAppResellerAccountResponse)
async def reseller_account(request: WebAppResellerCodeRequest) -> WebAppResellerAccountResponse:
    async def call() -> WebAppResellerAccountResponse:
        user_id = await _user(request)
        account, panel = await _owned(request.code, user_id)
        actions = account_actions(account, panel)
        response = WebAppResellerAccountResponse(
            account=_account_item(account, panel.name if panel else None),
            actions=sorted(actions),
            admin_locked=is_admin_locked(account),
            usage_cap_bytes=account.usage_cap_bytes,
            purchased_volume=account.purchased_volume,
        )

        try:
            info = await load_account_live_info(account)
            response.panel_url = info.login_url if ACTION_CREDENTIALS in actions else None
            response.used_traffic_bytes = info.used_traffic
            response.data_limit_bytes = info.data_limit
            response.total_users = info.total_users
            response.rate = info.live_rate
            response.balance = info.balance
            response.billed_total = info.billed_total
            response.grace_days_left = info.grace_days_left
        except Exception as exc:
            log.warning("webapp reseller live info failed code=%s: %s", account.code, exc)
            response.live = False

        if account.pricing_mode in PAYG_MODES:
            if response.balance is None:
                response.balance = await _balance(user_id)
            user_accounts = await ResellerAccountCRUD().get_accounts_by_user(user_id)
            runway = await estimate_runway(response.balance, user_accounts)
            response.runway_hours = round(runway.hours_left, 2) if runway.hours_left is not None else None

        if ACTION_RENEW in actions:
            response.renew_plans = [
                _renew_item(plan)
                for plan in await ResellerPlanManager().get_all_plans(panel_code=account.panel_code, enabled_only=True)
                if plan.pricing_mode == "fixed"
            ]
        if ACTION_BUY_CAPACITY in actions and panel:
            response.capacity_price_per_user = int(panel_reseller_capacity_settings(panel)["price_per_user"])
            response.capacity_presets = list(CAPACITY_PRESETS)

        events, _ = await ResellerEventCRUD().list_events(account_code=account.code, limit=10)
        response.events = [_event_item(event) for event in events]
        return response

    return await _run(WebAppResellerAccountResponse, call)


@router.post("/webapp/reseller/account/password", response_model=WebAppResellerPasswordResponse)
async def reseller_password(request: WebAppResellerCodeRequest) -> WebAppResellerPasswordResponse:
    async def call() -> WebAppResellerPasswordResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_CREDENTIALS)
        return WebAppResellerPasswordResponse(password=reveal_password(account))

    return await _run(WebAppResellerPasswordResponse, call)


@router.post("/webapp/reseller/account/password/reset", response_model=WebAppResellerPasswordResponse)
async def reseller_password_reset(request: WebAppResellerCodeRequest) -> WebAppResellerPasswordResponse:
    async def call() -> WebAppResellerPasswordResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_CHANGE_PASSWORD)
        ok, message, password = await reset_password(account, actor_id=user_id)
        if not ok:
            raise _Refused(message)
        return WebAppResellerPasswordResponse(password=password, message=message)

    return await _run(WebAppResellerPasswordResponse, call)


@router.post("/webapp/reseller/account/pause", response_model=WebAppResellerActionResponse)
async def reseller_pause(request: WebAppResellerCodeRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_PAUSE)
        ok, message = await pause_account(account)
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message)

    return await _run(WebAppResellerActionResponse, call)


@router.post("/webapp/reseller/account/resume", response_model=WebAppResellerActionResponse)
async def reseller_resume(request: WebAppResellerCodeRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_RESUME)
        ok, message = await resume_account(account)
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message)

    return await _run(WebAppResellerActionResponse, call)


@router.post("/webapp/reseller/account/renew/preview", response_model=WebAppResellerRenewPreviewResponse)
async def reseller_renew_preview(request: WebAppResellerRenewRequest) -> WebAppResellerRenewPreviewResponse:
    async def call() -> WebAppResellerRenewPreviewResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_RENEW)
        plan = await _renew_plan(account, request.plan_id)
        price, error = await apply_reseller_discount(user_id, calculate_purchase_price(plan), request.discount_code)
        if error:
            raise _Refused(error)
        balance = await _balance(user_id)
        return WebAppResellerRenewPreviewResponse(
            plan=_renew_item(plan),
            base_price=price.base_price,
            final_price=price.final_price,
            discount_percent=price.discount_percent,
            balance=balance,
            can_pay=balance >= price.final_price,
        )

    return await _run(WebAppResellerRenewPreviewResponse, call)


@router.post("/webapp/reseller/account/renew/confirm", response_model=WebAppResellerActionResponse)
async def reseller_renew_confirm(request: WebAppResellerRenewRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_RENEW)
        plan = await _renew_plan(account, request.plan_id)
        if not await acquire_user_lock(user_id, "reseller_renew", ttl=30):
            raise _Refused(LOCK_BUSY)
        try:
            price, error = await apply_reseller_discount(user_id, calculate_purchase_price(plan), request.discount_code)
            if error:
                raise _Refused(error)
            ok, message = await renew_reseller_account(
                account.code,
                plan.id,
                user_id,
                amount=price.final_price,
                discount_code=price.discount_code,
                actor_id=user_id,
            )
        finally:
            await release_user_lock(user_id, "reseller_renew")
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message, new_balance=await _balance(user_id))

    return await _run(WebAppResellerActionResponse, call)


@router.post("/webapp/reseller/account/usage-cap", response_model=WebAppResellerActionResponse)
async def reseller_usage_cap(request: WebAppResellerUsageCapRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_USAGE_CAP)
        gigabytes = request.usage_cap_gb if request.usage_cap_gb and request.usage_cap_gb > 0 else None
        ok, message = await set_reseller_usage_cap(account, gigabytes=gigabytes, actor_id=user_id)
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message)

    return await _run(WebAppResellerActionResponse, call)


@router.post("/webapp/reseller/account/capacity/preview", response_model=WebAppResellerCapacityPreviewResponse)
async def reseller_capacity_preview(request: WebAppResellerCapacityRequest) -> WebAppResellerCapacityPreviewResponse:
    async def call() -> WebAppResellerCapacityPreviewResponse:
        user_id = await _user(request)
        account, panel = await _owned(request.code, user_id, ACTION_BUY_CAPACITY)
        price_per_user = int(panel_reseller_capacity_settings(panel)["price_per_user"])
        total = calculate_capacity_price(panel, request.quantity, price_per_user=price_per_user)
        balance = await _balance(user_id)
        limit_before = int(account.max_users or 0)
        return WebAppResellerCapacityPreviewResponse(
            price_per_user=price_per_user,
            total_price=total,
            limit_before=limit_before,
            limit_after=limit_before + request.quantity,
            balance=balance,
            can_pay=balance >= total,
        )

    return await _run(WebAppResellerCapacityPreviewResponse, call)


@router.post("/webapp/reseller/account/capacity/confirm", response_model=WebAppResellerActionResponse)
async def reseller_capacity_confirm(request: WebAppResellerCapacityRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, panel = await _owned(request.code, user_id, ACTION_BUY_CAPACITY)
        # Same lock name as the bot, so a tap in Telegram and one in the web app can't both charge.
        if not await acquire_user_lock(user_id, "reseller_capacity_buy", ttl=20):
            raise _Refused(LOCK_BUSY)
        try:
            ok, message = await increase_reseller_capacity(
                account, panel, quantity=request.quantity, telegram_id=user_id, source="webapp"
            )
        finally:
            await release_user_lock(user_id, "reseller_capacity_buy")
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message, new_balance=await _balance(user_id))

    return await _run(WebAppResellerActionResponse, call)


@router.post("/webapp/reseller/account/usage", response_model=WebAppResellerUsageResponse)
async def reseller_usage(request: WebAppResellerPageRequest) -> WebAppResellerUsageResponse:
    """Charge history: what was used, at which rate, over which period."""

    async def call() -> WebAppResellerUsageResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_USAGE_REPORT)
        crud = ResellerBillingSnapshotCRUD()
        offset = (request.page - 1) * request.limit
        # One extra row tells whether another page exists.
        snapshots = await crud.get_snapshots(account.code, limit=request.limit + 1, offset=offset)
        _, total_billed = await crud.get_usage_totals(account.code)
        rows = [
            ResellerUsageRow(
                snapshot_at=entry.charged_at,
                period_start=entry.period_start,
                kind=entry.kind,
                used_bytes=entry.used_bytes or 0,
                billed_minutes=entry.minutes,
                unit_price=round(entry.unit_price, 2) if entry.unit_price is not None else None,
                rate_estimated=entry.rate_estimated,
                amount=entry.amount,
                is_debt=entry.is_debt,
            )
            for entry in await describe_charges(snapshots[: request.limit])
        ]
        return WebAppResellerUsageResponse(
            rows=rows, total_billed=total_billed, has_more=len(snapshots) > request.limit
        )

    return await _run(WebAppResellerUsageResponse, call)


@router.post("/webapp/reseller/account/events", response_model=WebAppResellerEventsResponse)
async def reseller_events(request: WebAppResellerPageRequest) -> WebAppResellerEventsResponse:
    """The account's own history (purchase, renewals, suspensions, ...)."""

    async def call() -> WebAppResellerEventsResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id)
        events, total = await ResellerEventCRUD().list_events(
            account_code=account.code, limit=request.limit, offset=(request.page - 1) * request.limit
        )
        return WebAppResellerEventsResponse(events=[_event_item(event) for event in events], total=total)

    return await _run(WebAppResellerEventsResponse, call)


@router.post("/webapp/reseller/account/delete", response_model=WebAppResellerActionResponse)
async def reseller_delete(request: WebAppResellerCodeRequest) -> WebAppResellerActionResponse:
    async def call() -> WebAppResellerActionResponse:
        user_id = await _user(request)
        account, _ = await _owned(request.code, user_id, ACTION_DELETE)
        ok, message = await delete_account(account, actor_id=user_id)
        if not ok:
            raise _Refused(message)
        return WebAppResellerActionResponse(message=message.replace("`", ""))

    return await _run(WebAppResellerActionResponse, call)

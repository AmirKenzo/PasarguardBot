"""Read queries for the panel pages."""

from __future__ import annotations

import time
from bisect import bisect_right
from typing import Any

from sqlalchemy import BigInteger, String, case, cast, func, literal, or_, select, union_all

from app.db.base import AsyncSessionLocal as Session
from app.db.models.cryptopayments import CryptoPayments
from app.db.models.discount_codes import DiscountCode
from app.db.models.panels import Panels
from app.db.models.plans import Plan
from app.db.models.referral import ReferralReward
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.reseller_events import ResellerEvent
from app.db.models.reseller_plans import ResellerPlan
from app.db.models.services import Service
from app.db.models.stars_transaction import StarsTransaction
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.models.zarinpal_payment import ZarinpalPayment
from app.services.billing import payment_stats

INACTIVE_STATUSES = ("ban", "BlockedBot", "DeleteAccount")
# Status the bot writes when a deposit is approved.
APPROVED_STATUS = "approved"
DAY = 86400


def _page_bounds(page: int, per_page: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    return (page - 1) * per_page, per_page


def pages_for(total: int, per_page: int) -> int:
    return max(1, -(-int(total or 0) // per_page))


# --------------------------------------------------------------------------- #
#  Dashboard                                                                    #
# --------------------------------------------------------------------------- #


async def dashboard_stats() -> dict[str, Any]:
    now = int(time.time())
    today_start = int(payment_stats.tehran_day_start().timestamp())
    async with Session() as session:
        users_total = int((await session.execute(select(func.count()).select_from(User))).scalar() or 0)
        users_blocked = int(
            (
                await session.execute(select(func.count()).select_from(User).where(User.status.in_(INACTIVE_STATUSES)))
            ).scalar()
            or 0
        )
        users_today = int(
            (await session.execute(select(func.count()).select_from(User).where(User.time_s >= today_start))).scalar()
            or 0
        )
        wallet_total = int((await session.execute(select(func.coalesce(func.sum(User.amount), 0)))).scalar() or 0)

        services_total = int((await session.execute(select(func.count()).select_from(Service))).scalar() or 0)
        services_active = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Service)
                    .where(
                        Service.enable.is_(True), or_(Service.expiration_time.is_(None), Service.expiration_time > now)
                    )
                )
            ).scalar()
            or 0
        )
        services_expired = max(0, services_total - services_active)

        pending_tx = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.status == "pending", Transaction.method == "manual")
                )
            ).scalar()
            or 0
        )
        panels_total = int((await session.execute(select(func.count()).select_from(Panels))).scalar() or 0)
        resellers_active = int(
            (
                await session.execute(
                    select(func.count()).select_from(ResellerAccount).where(ResellerAccount.status == "active")
                )
            ).scalar()
            or 0
        )

    # Income counts paid top-ups from every gateway, by payment time.
    income_today = (await payment_stats.method_totals(today_start))["total"]["total_amount"]
    income_month = (await payment_stats.method_totals(now - 30 * DAY))["total"]["total_amount"]

    return {
        "users_total": users_total,
        "users_blocked": users_blocked,
        "users_today": users_today,
        "wallet_total": wallet_total,
        "services_total": services_total,
        "services_active": services_active,
        "services_expired": services_expired,
        "income_today": income_today,
        "income_month": income_month,
        "pending_tx": pending_tx,
        "panels_total": panels_total,
        "resellers_active": resellers_active,
    }


async def sidebar_badges() -> dict[str, int]:
    """Counts shown next to sidebar entries."""
    async with Session() as session:
        pending = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.status == "pending", Transaction.method == "manual")
                )
            ).scalar()
            or 0
        )
    return {"transactions": pending} if pending else {}


async def daily_series(days: int = 14) -> list[dict[str, Any]]:
    """Per-day (Tehran calendar) revenue from every gateway and signup counts for the dashboard chart."""
    boundaries = payment_stats.tehran_day_boundaries(days)
    revenue = await payment_stats.bucket_revenue(boundaries)
    async with Session() as session:
        user_rows = (
            await session.execute(select(User.time_s).where(User.time_s >= boundaries[0], User.time_s < boundaries[-1]))
        ).all()

    signups = [0] * days
    for (time_s,) in user_rows:
        if time_s:
            signups[bisect_right(boundaries, int(time_s)) - 1] += 1

    return [{"ts": boundaries[index], "revenue": revenue[index], "signups": signups[index]} for index in range(days)]


# --------------------------------------------------------------------------- #
#  Users                                                                        #
# --------------------------------------------------------------------------- #


# Maps the API's `state` filter to the raw `User.status` value it corresponds to.
USER_STATE_TO_STATUS = {"banned": "ban", "blocked_bot": "BlockedBot", "deleted": "DeleteAccount"}


async def list_users(*, q: str = "", state: str = "", page: int = 1, per_page: int = 25, sort: str = "newest"):
    offset, limit = _page_bounds(page, per_page)
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(cast(User.id, String).like(like), User.number.like(like)))
    if state == "active":
        filters.append(or_(User.status.is_(None), User.status.notin_(INACTIVE_STATUSES)))
    elif state in USER_STATE_TO_STATUS:
        filters.append(User.status == USER_STATE_TO_STATUS[state])

    order = User.time_s.asc() if sort == "oldest" else User.time_s.desc()
    async with Session() as session:
        base = select(User)
        counter = select(func.count()).select_from(User)
        for condition in filters:
            base = base.where(condition)
            counter = counter.where(condition)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (await session.execute(base.order_by(order, User.id.desc()).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def get_user(user_id: int) -> User | None:
    async with Session() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalars().first()


async def user_services(user_id: int) -> list[Service]:
    async with Session() as session:
        result = await session.execute(select(Service).where(Service.id == user_id).order_by(Service.createtime.desc()))
        return list(result.scalars().all())


async def user_transactions(user_id: int, limit: int = 20) -> list[Transaction]:
    async with Session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.id.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def user_referrals(user_id: int) -> int:
    async with Session() as session:
        result = await session.execute(select(func.count()).select_from(User).where(User.ref == user_id))
        return int(result.scalar() or 0)


# --------------------------------------------------------------------------- #
#  Services                                                                     #
# --------------------------------------------------------------------------- #


async def list_services(*, q: str = "", panel: str = "", state: str = "", page: int = 1, per_page: int = 25):
    offset, limit = _page_bounds(page, per_page)
    now = int(time.time())
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Service.username.like(like), cast(Service.id, String).like(like)))
    if panel.isdigit():
        filters.append(Service.in_panel == int(panel))
    if state == "active":
        filters.append(Service.enable.is_(True))
        filters.append(or_(Service.expiration_time.is_(None), Service.expiration_time > now))
    elif state == "expired":
        filters.append(or_(Service.enable.is_(False), Service.expiration_time <= now))
    elif state == "test":
        filters.append(Service.is_test.is_(True))

    async with Session() as session:
        base = select(Service)
        counter = select(func.count()).select_from(Service)
        for condition in filters:
            base = base.where(condition)
            counter = counter.where(condition)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (
            (
                await session.execute(
                    base.order_by(Service.createtime.desc(), Service.code.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
    return list(rows), total


async def get_service(code: int) -> Service | None:
    async with Session() as session:
        return (await session.execute(select(Service).where(Service.code == code))).scalars().first()


# --------------------------------------------------------------------------- #
#  Transactions / crypto                                                        #
# --------------------------------------------------------------------------- #


def _tx_branch():
    normalized_status = case(
        (Transaction.status == "approved", "approved"),
        (Transaction.status == "rejected", "rejected"),
        (Transaction.status == "needs_fix", "needs_fix"),
        else_="pending",
    )
    normalized_method = case(
        (Transaction.method == "manual", "manual_card"),
        else_=Transaction.method,
    )
    return select(
        cast(Transaction.id, String).label("raw_id"),
        literal("tx").label("source"),
        normalized_method.label("method"),
        Transaction.user_id.label("user_id"),
        cast(Transaction.amount, BigInteger).label("amount"),
        normalized_status.label("status"),
        Transaction.created_at.label("created_at"),
    )


def _crypto_branch():
    normalized_status = case(
        (CryptoPayments.status == "Paid", "approved"),
        (CryptoPayments.status == "Pending", "pending"),
        else_="expired",
    )
    return select(
        cast(CryptoPayments.order_id, String).label("raw_id"),
        literal("crypto").label("source"),
        literal("crypto").label("method"),
        CryptoPayments.user_id.label("user_id"),
        cast(CryptoPayments.amount_irt, BigInteger).label("amount"),
        normalized_status.label("status"),
        CryptoPayments.createtime.label("created_at"),
    )


def _stars_branch():
    normalized_status = case(
        (StarsTransaction.status == "approved", "approved"),
        (StarsTransaction.status == "pending", "pending"),
        else_="expired",
    )
    return select(
        cast(StarsTransaction.id, String).label("raw_id"),
        literal("stars").label("source"),
        literal("stars").label("method"),
        StarsTransaction.user_id.label("user_id"),
        cast(StarsTransaction.amount, BigInteger).label("amount"),
        normalized_status.label("status"),
        StarsTransaction.created_at.label("created_at"),
    )


def _tonpays_branch():
    normalized_status = case(
        (TonPaysInvoice.status == "completed", "approved"),
        (TonPaysInvoice.status.in_(("pending", "processing", "need_action")), "pending"),
        (TonPaysInvoice.status == "rejected", "rejected"),
        else_="expired",
    )
    return select(
        cast(TonPaysInvoice.id, String).label("raw_id"),
        literal("tonpays").label("source"),
        literal("tonpays").label("method"),
        TonPaysInvoice.user_id.label("user_id"),
        cast(TonPaysInvoice.amount, BigInteger).label("amount"),
        normalized_status.label("status"),
        TonPaysInvoice.created_at.label("created_at"),
    )


def _zarinpal_branch():
    normalized_status = case(
        (ZarinpalPayment.status == "completed", "approved"),
        (ZarinpalPayment.status == "pending", "pending"),
        (ZarinpalPayment.status == "failed", "rejected"),
        else_="expired",
    )
    return select(
        cast(ZarinpalPayment.id, String).label("raw_id"),
        literal("zarinpal").label("source"),
        literal("zarinpal").label("method"),
        ZarinpalPayment.user_id.label("user_id"),
        cast(ZarinpalPayment.amount, BigInteger).label("amount"),
        normalized_status.label("status"),
        ZarinpalPayment.created_at.label("created_at"),
    )


def _unified(name: str):
    return union_all(_tx_branch(), _crypto_branch(), _stars_branch(), _tonpays_branch(), _zarinpal_branch()).subquery(
        name
    )


async def list_unified_transactions(
    *,
    tx_id: str = "",
    user_id: str = "",
    amount: str = "",
    method: str = "",
    status: str = "",
    days: int = 0,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[Any], int]:
    """Every payment method in one feed: card-to-card, crypto, Stars and TonPays.

    Only manual-card rows are ever actionable (crypto confirms itself) — that
    distinction is made by the caller from ``method``/``status``, not here.
    """
    offset, limit = _page_bounds(page, per_page)
    combined = _unified("unified_tx")

    conditions = []
    if tx_id.strip():
        conditions.append(combined.c.raw_id == tx_id.strip())
    if user_id.strip():
        conditions.append(cast(combined.c.user_id, String) == user_id.strip())
    if amount.strip().isdigit():
        conditions.append(combined.c.amount == int(amount.strip()))
    if method:
        conditions.append(combined.c.method == method)
    if status:
        conditions.append(combined.c.status == status)
    if days > 0:
        conditions.append(combined.c.created_at >= int(time.time()) - days * DAY)

    stmt = select(combined)
    counter = select(func.count()).select_from(combined)
    for condition in conditions:
        stmt = stmt.where(condition)
        counter = counter.where(condition)

    async with Session() as session:
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (await session.execute(stmt.order_by(combined.c.created_at.desc()).limit(limit).offset(offset))).all()
    return list(rows), total


async def transaction_stats() -> dict[str, int]:
    """Numbers for the transactions page's stat tiles."""
    combined = _unified("unified_tx_stats")
    week_ago = int(time.time()) - 7 * DAY

    async with Session() as session:
        pending = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Transaction)
                    .where(Transaction.status == "pending", Transaction.method == "manual")
                )
            ).scalar()
            or 0
        )
        rejected_7d = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(combined)
                    .where(combined.c.status == "rejected", combined.c.created_at >= week_ago)
                )
            ).scalar()
            or 0
        )

    paid_7d = (await payment_stats.method_totals(week_ago))["total"]
    approved_7d = paid_7d["count"]
    approved_volume_7d = paid_7d["total_amount"]

    return {
        "pending": pending,
        "approved_7d": approved_7d,
        "rejected_7d": rejected_7d,
        "approved_volume_7d": approved_volume_7d,
    }


async def get_transaction(tx_id: int) -> Transaction | None:
    async with Session() as session:
        return (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalars().first()


async def list_crypto_payments(*, status: str = "", page: int = 1, per_page: int = 25):
    offset, limit = _page_bounds(page, per_page)
    async with Session() as session:
        base = select(CryptoPayments)
        counter = select(func.count()).select_from(CryptoPayments)
        if status:
            base = base.where(CryptoPayments.status == status)
            counter = counter.where(CryptoPayments.status == status)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (
            (await session.execute(base.order_by(CryptoPayments.createtime.desc()).limit(limit).offset(offset)))
            .scalars()
            .all()
        )
    return list(rows), total


# --------------------------------------------------------------------------- #
#  Panels / plans                                                               #
# --------------------------------------------------------------------------- #


async def list_panels() -> list[Panels]:
    async with Session() as session:
        return list((await session.execute(select(Panels).order_by(Panels.code))).scalars().all())


async def get_panel(code: int) -> Panels | None:
    async with Session() as session:
        return (await session.execute(select(Panels).where(Panels.code == code))).scalars().first()


async def panel_names() -> dict[int, str]:
    async with Session() as session:
        rows = (await session.execute(select(Panels.code, Panels.name))).all()
    return {int(code): str(name) for code, name in rows}


async def panel_names_for(codes: set[int]) -> dict[int, str]:
    if not codes:
        return {}
    async with Session() as session:
        rows = (await session.execute(select(Panels.code, Panels.name).where(Panels.code.in_(codes)))).all()
    return {int(code): str(name) for code, name in rows}


async def list_panel_options(
    *, fields: tuple[str, ...], q: str = "", page: int = 1, per_page: int = 25
) -> tuple[list[Any], int]:
    offset, limit = _page_bounds(page, per_page)
    columns = [getattr(Panels, field) for field in fields]
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Panels.name.like(like), Panels.base_url.like(like)))

    async with Session() as session:
        stmt = select(*columns)
        counter = select(func.count()).select_from(Panels)
        for condition in filters:
            stmt = stmt.where(condition)
            counter = counter.where(condition)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (await session.execute(stmt.order_by(Panels.code).limit(limit).offset(offset))).all()
    return list(rows), total


PLAN_SORTS = {
    "newest": lambda: Plan.id.desc(),
    "oldest": lambda: Plan.id.asc(),
    "price_asc": lambda: Plan.price.asc(),
    "price_desc": lambda: Plan.price.desc(),
    "volume_asc": lambda: Plan.storage.asc(),
    "volume_desc": lambda: Plan.storage.desc(),
    "duration_asc": lambda: Plan.duration.asc(),
    "duration_desc": lambda: Plan.duration.desc(),
}


async def list_plans(
    panel: str = "", *, page: int = 1, per_page: int = 25, sort: str = "newest"
) -> tuple[list[Plan], int]:
    offset, limit = _page_bounds(page, per_page)
    order = PLAN_SORTS.get(sort, PLAN_SORTS["newest"])()

    async with Session() as session:
        stmt = select(Plan)
        counter = select(func.count()).select_from(Plan)
        if panel.isdigit():
            condition = Plan.panel_code == int(panel)
            stmt = stmt.where(condition)
            counter = counter.where(condition)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (await session.execute(stmt.order_by(order).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def get_plan(plan_id: int) -> Plan | None:
    async with Session() as session:
        return (await session.execute(select(Plan).where(Plan.id == plan_id))).scalars().first()


# --------------------------------------------------------------------------- #
#  Resellers                                                                    #
# --------------------------------------------------------------------------- #


async def list_resellers(
    *,
    status: str = "",
    q: str = "",
    panel_code: int | None = None,
    pricing_mode: str = "",
    page: int = 1,
    per_page: int = 25,
):
    offset, limit = _page_bounds(page, per_page)
    filters = []
    if status:
        filters.append(ResellerAccount.status == status)
    if panel_code:
        filters.append(ResellerAccount.panel_code == panel_code)
    if pricing_mode:
        filters.append(ResellerAccount.pricing_mode == pricing_mode)
    if q:
        like = f"%{q}%"
        filters.append(or_(ResellerAccount.username.like(like), cast(ResellerAccount.telegram_id, String).like(like)))
    async with Session() as session:
        base = select(ResellerAccount)
        counter = select(func.count()).select_from(ResellerAccount)
        for condition in filters:
            base = base.where(condition)
            counter = counter.where(condition)
        total = int((await session.execute(counter)).scalar() or 0)
        rows = (
            (await session.execute(base.order_by(ResellerAccount.code.desc()).limit(limit).offset(offset)))
            .scalars()
            .all()
        )
    return list(rows), total


async def get_reseller(code: int) -> ResellerAccount | None:
    async with Session() as session:
        return (await session.execute(select(ResellerAccount).where(ResellerAccount.code == code))).scalars().first()


async def reseller_snapshots(code: int, limit: int = 20) -> list[ResellerBillingSnapshot]:
    async with Session() as session:
        result = await session.execute(
            select(ResellerBillingSnapshot)
            .where(ResellerBillingSnapshot.account_code == code)
            .order_by(ResellerBillingSnapshot.snapshot_at.desc(), ResellerBillingSnapshot.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def reseller_breakdown() -> list[tuple[str, str, int]]:
    """(status, pricing_mode, count) for every combination that has accounts."""
    async with Session() as session:
        rows = await session.execute(
            select(ResellerAccount.status, ResellerAccount.pricing_mode, func.count()).group_by(
                ResellerAccount.status, ResellerAccount.pricing_mode
            )
        )
        return [(str(status), str(mode), int(count)) for status, mode, count in rows.all()]


async def burning_resellers(modes: tuple[str, ...]) -> list[ResellerAccount]:
    async with Session() as session:
        result = await session.execute(
            select(ResellerAccount).where(ResellerAccount.status == "active", ResellerAccount.pricing_mode.in_(modes))
        )
        return list(result.scalars().all())


async def resellers_expiring(until: int, statuses: tuple[str, ...]) -> list[ResellerAccount]:
    """Accounts in ``statuses`` whose expiry falls before ``until``, soonest first."""
    async with Session() as session:
        result = await session.execute(
            select(ResellerAccount)
            .where(
                ResellerAccount.expiration_time.is_not(None),
                ResellerAccount.expiration_time <= until,
                ResellerAccount.status.in_(statuses),
            )
            .order_by(ResellerAccount.expiration_time.asc())
            .limit(100)
        )
        return list(result.scalars().all())


async def user_balances(user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    async with Session() as session:
        rows = await session.execute(select(User.id, User.amount).where(User.id.in_(user_ids)))
        return {int(user_id): int(amount or 0) for user_id, amount in rows.all()}


async def reseller_billed_buckets(boundaries: list[int]) -> list[int]:
    """Pay-as-you-go charges per ``[boundaries[i], boundaries[i+1])`` window."""
    totals = [0] * (len(boundaries) - 1)
    async with Session() as session:
        rows = await session.execute(
            select(ResellerBillingSnapshot.snapshot_at, ResellerBillingSnapshot.billed_amount).where(
                ResellerBillingSnapshot.snapshot_at >= boundaries[0],
                ResellerBillingSnapshot.snapshot_at < boundaries[-1],
                ResellerBillingSnapshot.billed_amount > 0,
            )
        )
        for snapshot_at, amount in rows.all():
            totals[bisect_right(boundaries, int(snapshot_at)) - 1] += int(amount or 0)
    return totals


async def reseller_events_between(since: int, until: int, kinds: tuple[str, ...]) -> list[ResellerEvent]:
    async with Session() as session:
        result = await session.execute(
            select(ResellerEvent).where(
                ResellerEvent.created_at >= since,
                ResellerEvent.created_at < until,
                ResellerEvent.kind.in_(kinds),
            )
        )
        return list(result.scalars().all())


async def reseller_ledger(
    *,
    account_code: int | None = None,
    telegram_id: int | None = None,
    since: int | None = None,
    until: int | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[tuple[ResellerBillingSnapshot, ResellerAccount | None]], int, int]:
    """Charged ledger rows newest first with their account. Returns (rows, total_rows, total_billed)."""
    offset, limit = _page_bounds(page, per_page)
    filters = [ResellerBillingSnapshot.billed_amount > 0]
    if account_code:
        filters.append(ResellerBillingSnapshot.account_code == account_code)
    if telegram_id:
        filters.append(ResellerAccount.telegram_id == telegram_id)
    if since:
        filters.append(ResellerBillingSnapshot.snapshot_at >= since)
    if until:
        filters.append(ResellerBillingSnapshot.snapshot_at < until)
    joined = ResellerBillingSnapshot.__table__.outerjoin(
        ResellerAccount.__table__, ResellerAccount.code == ResellerBillingSnapshot.account_code
    )
    async with Session() as session:
        total, billed = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(ResellerBillingSnapshot.billed_amount), 0))
                .select_from(joined)
                .where(*filters)
            )
        ).one()
        rows = (
            await session.execute(
                select(ResellerBillingSnapshot, ResellerAccount)
                .select_from(joined)
                .where(*filters)
                .order_by(ResellerBillingSnapshot.snapshot_at.desc(), ResellerBillingSnapshot.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    return [(snapshot, account) for snapshot, account in rows], int(total or 0), int(billed or 0)


async def reseller_plan_link_counts() -> dict[int, int]:
    async with Session() as session:
        rows = await session.execute(
            select(ResellerAccount.plan_id, func.count())
            .where(ResellerAccount.plan_id.is_not(None))
            .group_by(ResellerAccount.plan_id)
        )
        return {int(plan_id): int(count) for plan_id, count in rows.all()}


async def list_reseller_plans() -> list[ResellerPlan]:
    async with Session() as session:
        return list(
            (await session.execute(select(ResellerPlan).order_by(ResellerPlan.panel_code, ResellerPlan.id)))
            .scalars()
            .all()
        )


async def get_reseller_plan(plan_id: int) -> ResellerPlan | None:
    async with Session() as session:
        return (await session.execute(select(ResellerPlan).where(ResellerPlan.id == plan_id))).scalars().first()


# --------------------------------------------------------------------------- #
#  Discounts                                                                    #
# --------------------------------------------------------------------------- #


async def list_discounts(*, page: int = 1, per_page: int = 25):
    offset, limit = _page_bounds(page, per_page)
    async with Session() as session:
        total = int((await session.execute(select(func.count()).select_from(DiscountCode))).scalar() or 0)
        rows = (
            (await session.execute(select(DiscountCode).order_by(DiscountCode.id.desc()).limit(limit).offset(offset)))
            .scalars()
            .all()
        )
    return list(rows), total


async def get_discount(code_id: int) -> DiscountCode | None:
    async with Session() as session:
        return (await session.execute(select(DiscountCode).where(DiscountCode.id == code_id))).scalars().first()


async def get_discount_by_code(code: str) -> DiscountCode | None:
    async with Session() as session:
        return (await session.execute(select(DiscountCode).where(DiscountCode.code == code))).scalars().first()


# --------------------------------------------------------------------------- #
#  Referral                                                                     #
# --------------------------------------------------------------------------- #


async def referral_rewards(*, page: int = 1, per_page: int = 25):
    """Paginated reward history plus the running totals shown above it."""
    offset, limit = _page_bounds(page, per_page)
    async with Session() as session:
        total = int((await session.execute(select(func.count()).select_from(ReferralReward))).scalar() or 0)
        paid = int(
            (await session.execute(select(func.coalesce(func.sum(ReferralReward.reward_amount), 0)))).scalar() or 0
        )
        bonus = int(
            (await session.execute(select(func.coalesce(func.sum(ReferralReward.bonus_amount), 0)))).scalar() or 0
        )
        rows = (
            (
                await session.execute(
                    select(ReferralReward).order_by(ReferralReward.id.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
    return list(rows), total, paid, bonus

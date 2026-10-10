"""Read-side payment statistics across every gateway that credits user balance.

One place defines, per gateway, which rows count as paid, which column holds the credited
toman amount (bonus excluded) and when the payment was paid. Every stats surface (bot,
web app, admin panel) should read through here so their numbers agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, literal, select, union_all

from app.db.base import AsyncSessionLocal as Session
from app.db.models.cryptopayments import CryptoPayments
from app.db.models.stars_transaction import StarsTransaction
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.db.models.transaction import Transaction
from app.db.models.zarinpal_payment import ZarinpalPayment

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

METHODS: tuple[str, ...] = ("manual", "crypto", "stars", "tonpays", "zarinpal")
METHOD_LABELS_FA: dict[str, str] = {
    "manual": "کارت‌به‌کارت دستی",
    "crypto": "ارز دیجیتال",
    "stars": "استارز",
    "tonpays": "TonPays",
    "zarinpal": "زرین‌پال",
}


@dataclass(frozen=True)
class _Source:
    method: str
    user_id: Any
    amount: Any
    paid_at: Any
    paid: Any


def _sources() -> list[_Source]:
    tx_paid_at = func.coalesce(Transaction.completed_at, Transaction.created_at)
    return [
        _Source(
            "manual",
            Transaction.user_id,
            Transaction.amount,
            tx_paid_at,
            (Transaction.status == "approved") & (Transaction.method == "manual"),
        ),
        _Source(
            "crypto",
            CryptoPayments.user_id,
            CryptoPayments.amount_irt,
            func.coalesce(func.nullif(CryptoPayments.paytime, 0), CryptoPayments.createtime),
            CryptoPayments.status == "Paid",
        ),
        _Source(
            "stars",
            StarsTransaction.user_id,
            StarsTransaction.amount,
            func.coalesce(StarsTransaction.paid_at, StarsTransaction.created_at),
            StarsTransaction.status == "approved",
        ),
        _Source(
            "tonpays",
            TonPaysInvoice.user_id,
            TonPaysInvoice.amount,
            func.coalesce(TonPaysInvoice.paid_at, TonPaysInvoice.created_at),
            TonPaysInvoice.status == "completed",
        ),
        # Sandbox (test-mode) payments move no real money, so they never count as revenue.
        _Source(
            "zarinpal",
            ZarinpalPayment.user_id,
            ZarinpalPayment.amount,
            func.coalesce(ZarinpalPayment.paid_at, ZarinpalPayment.created_at),
            (ZarinpalPayment.status == "completed") & ZarinpalPayment.sandbox.is_(False),
        ),
    ]


def paid_payments(start_ts: int | None = None, end_ts: int | None = None, user_id: int | None = None):
    """Subquery of every paid top-up: (method, user_id, amount, paid_at), optionally filtered."""
    selects = []
    for source in _sources():
        conditions = [source.paid]
        if start_ts:
            conditions.append(source.paid_at >= start_ts)
        if end_ts is not None:
            conditions.append(source.paid_at < end_ts)
        if user_id is not None:
            conditions.append(source.user_id == user_id)
        selects.append(
            select(
                literal(source.method).label("method"),
                source.user_id.label("user_id"),
                source.amount.label("amount"),
                source.paid_at.label("paid_at"),
            ).where(*conditions)
        )
    return union_all(*selects).subquery("paid_payments")


def _empty_totals() -> dict[str, dict[str, int]]:
    return {method: {"count": 0, "total_amount": 0} for method in (*METHODS, "total")}


async def method_totals(
    start_ts: int | None = None, end_ts: int | None = None, user_id: int | None = None
) -> dict[str, dict[str, int]]:
    """Paid `{count, total_amount}` per gateway plus `total`, for a period and/or one user."""
    paid = paid_payments(start_ts, end_ts, user_id)
    stmt = select(paid.c.method, func.count(), func.coalesce(func.sum(paid.c.amount), 0)).group_by(paid.c.method)
    totals = _empty_totals()
    async with Session() as session:
        for method, count, amount in (await session.execute(stmt)).all():
            totals[method] = {"count": int(count or 0), "total_amount": int(amount or 0)}
            totals["total"]["count"] += int(count or 0)
            totals["total"]["total_amount"] += int(amount or 0)
    return totals


async def bucket_revenue(boundaries: list[int]) -> list[int]:
    """Paid revenue (all gateways) in each [boundaries[i], boundaries[i+1]) window."""
    if len(boundaries) < 2:
        return []
    paid = paid_payments(boundaries[0], boundaries[-1])
    columns = [
        func.coalesce(
            func.sum(case(((paid.c.paid_at >= lo) & (paid.c.paid_at < hi), paid.c.amount), else_=0)),
            0,
        )
        for lo, hi in pairwise(boundaries)
    ]
    async with Session() as session:
        row = (await session.execute(select(*columns))).one()
    return [int(value or 0) for value in row]


async def top_users(
    start_ts: int | None = None, end_ts: int | None = None, *, by: str = "amount", limit: int = 10
) -> list[tuple[int, int, int]]:
    """Users ranked by paid top-ups across all gateways: [(user_id, total_amount, count)]."""
    paid = paid_payments(start_ts, end_ts)
    total = func.coalesce(func.sum(paid.c.amount), 0).label("total")
    count = func.count().label("cnt")
    order = (count.desc(), total.desc()) if by == "count" else (total.desc(), count.desc())
    stmt = select(paid.c.user_id, total, count).group_by(paid.c.user_id).order_by(*order).limit(limit)
    async with Session() as session:
        rows = (await session.execute(stmt)).all()
    return [(int(uid), int(amount or 0), int(cnt or 0)) for uid, amount, cnt in rows]


def tehran_day_start(now: datetime | None = None) -> datetime:
    value = (now or datetime.now(TEHRAN_TZ)).astimezone(TEHRAN_TZ)
    return datetime(value.year, value.month, value.day, tzinfo=TEHRAN_TZ)


def tehran_day_boundaries(days: int, now: datetime | None = None) -> list[int]:
    """Timestamps of the last `days` Tehran midnights up to tomorrow's, oldest first (days + 1 values)."""
    tomorrow = tehran_day_start(now) + timedelta(days=1)
    return [int((tomorrow - timedelta(days=offset)).timestamp()) for offset in range(days, -1, -1)]

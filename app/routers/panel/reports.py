"""Sales and customer reports."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request

from app.db.crud.services import ServiceCRUD
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.models.panel.reports import (
    REPORT_PERIODS,
    PanelRankRow,
    PanelReportsRequest,
    PanelReportsResponse,
    PanelReportTotals,
)
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor

router = APIRouter()

DAY = 86400


def _period_start(period: str) -> int:
    now = int(time.time())
    today = now - (now % DAY)
    if period == "week":
        return today - 6 * DAY
    if period == "month":
        return today - 29 * DAY
    return today


def _ranked(rows, *, amount_index: int, count_index: int | None) -> list[PanelRankRow]:
    return [
        PanelRankRow(
            rank=index,
            user_id=row[0],
            amount=int(row[amount_index] or 0),
            count=int(row[count_index] or 0) if count_index is not None else 0,
        )
        for index, row in enumerate(rows, start=1)
    ]


@router.post("/panel/reports", response_model=PanelReportsResponse)
async def reports(payload: PanelReportsRequest, request: Request) -> PanelReportsResponse:
    async def handle(_: PanelActor) -> PanelReportsResponse:
        period = payload.period if payload.period in REPORT_PERIODS else "today"
        start = _period_start(period)

        transactions = TransactionCRUD()
        services = ServiceCRUD()

        top_recharge, top_spenders, top_configs, breakdown, service_stats, new_users = await asyncio.gather(
            transactions.get_top_recharge_today(start, limit=10),
            transactions.get_top_spenders_today(start, limit=10),
            services.get_top_customers_by_config_count(limit=10),
            transactions.get_breakdown(start),
            services.get_period_stats(start),
            UserCRUD().count_since(start),
        )

        return PanelReportsResponse(
            period=period,
            period_start=start,
            totals=PanelReportTotals(
                new_users=int(new_users or 0),
                services_sold=int(service_stats.get("paid_period", 0)),
                test_services=int(service_stats.get("test_period", 0)),
                manual_approved_sum=int(breakdown.get("manual_approved_sum", 0)),
                auto_approved_sum=int(breakdown.get("auto_approved_sum", 0)),
                pending_sum=int(breakdown.get("manual_pending_total_sum", 0)),
                pending_count=int(breakdown.get("manual_pending_total_count", 0)),
            ),
            # get_top_recharge_today returns (user_id, tx_count, total_amount)
            top_recharge=_ranked(top_recharge, amount_index=2, count_index=1),
            # get_top_spenders_today returns (user_id, total_amount, tx_count)
            top_spenders=_ranked(top_spenders, amount_index=1, count_index=2),
            # get_top_customers_by_config_count returns (user_id, service_count)
            top_service_counts=[
                PanelRankRow(rank=index, user_id=row[0], count=int(row[1] or 0))
                for index, row in enumerate(top_configs, start=1)
            ],
        )

    return await guard.run(payload, request, PanelReportsResponse, handle)

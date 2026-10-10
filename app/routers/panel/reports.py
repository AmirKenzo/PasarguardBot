"""Sales and customer reports."""

from __future__ import annotations

import asyncio

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
from app.services.billing import payment_stats
from app.services.payments.ir_gateways.providers import GATEWAYS

router = APIRouter()

DAY = 86400


def _period_start(period: str) -> int:
    today = int(payment_stats.tehran_day_start().timestamp())
    if period == "3d":
        return today - 2 * DAY
    if period == "week":
        return today - 6 * DAY
    if period == "month":
        return today - 29 * DAY
    if period == "quarter":
        return today - 89 * DAY
    if period == "year":
        return today - 364 * DAY
    if period == "all":
        return 0
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

        top_recharge, top_spenders, top_configs, breakdown, service_stats, new_users, paid = await asyncio.gather(
            payment_stats.top_users(start or None, by="count", limit=10),
            payment_stats.top_users(start or None, by="amount", limit=10),
            services.get_top_customers_by_config_count(limit=10),
            transactions.get_breakdown(start),
            services.get_period_stats(start),
            UserCRUD().count_since(start),
            payment_stats.method_totals(start or None),
        )

        return PanelReportsResponse(
            period=period,
            period_start=start,
            totals=PanelReportTotals(
                new_users=int(new_users or 0),
                services_sold=int(service_stats.get("paid_period", 0)),
                test_services=int(service_stats.get("test_period", 0)),
                manual_approved_sum=paid["manual"]["total_amount"],
                auto_approved_sum=int(breakdown.get("auto_approved_sum", 0)),
                crypto_approved_sum=paid["crypto"]["total_amount"],
                stars_approved_sum=paid["stars"]["total_amount"],
                tonpays_approved_sum=paid["tonpays"]["total_amount"],
                ir_gateway_sums={key: paid[key]["total_amount"] for key in GATEWAYS},
                total_revenue=paid["total"]["total_amount"],
                pending_sum=int(breakdown.get("manual_pending_total_sum", 0)),
                pending_count=int(breakdown.get("manual_pending_total_count", 0)),
            ),
            # payment_stats.top_users returns (user_id, total_amount, count), every gateway
            top_recharge=_ranked(top_recharge, amount_index=1, count_index=2),
            top_spenders=_ranked(top_spenders, amount_index=1, count_index=2),
            # get_top_customers_by_config_count returns (user_id, service_count)
            top_service_counts=[
                PanelRankRow(rank=index, user_id=row[0], count=int(row[1] or 0))
                for index, row in enumerate(top_configs, start=1)
            ],
        )

    return await guard.run(payload, request, PanelReportsResponse, handle)

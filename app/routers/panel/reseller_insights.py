"""Reseller overview (counts, revenue, at-risk wallets, expiring accounts), billing ledger and event history."""

from __future__ import annotations

import time
from bisect import bisect_right

from fastapi import APIRouter, Request

from app.db.crud.reseller_accounts import EXPIRABLE_STATUSES
from app.db.crud.reseller_events import ResellerEventCRUD
from app.db.crud.settings import SettingsManager
from app.models.panel.common import PanelRequest, page_meta
from app.models.panel.resellers import (
    PanelResellerDayPoint,
    PanelResellerEventsRequest,
    PanelResellerEventsResponse,
    PanelResellerExpiringRow,
    PanelResellerLedgerRequest,
    PanelResellerLedgerResponse,
    PanelResellerOverviewResponse,
    PanelResellerRevenue,
    PanelResellerRunwayRow,
)
from app.panel import queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.routers.panel.resellers import event_row, snapshot_row
from app.services.billing import payment_stats
from app.services.reseller.accounts import grace_seconds
from app.services.reseller.logging import EVENT_KINDS, SALE_EVENT_KINDS
from app.services.reseller.runway import BURNING_MODES, estimate_runways

router = APIRouter()

REVENUE_DAYS = 30
SERIES_DAYS = 14
EXPIRING_WINDOW = 3 * 86400
AT_RISK_MIN_HOURS = 24
AT_RISK_LIMIT = 50


def _event_amount(event) -> int:
    try:
        return max(0, int(ResellerEventCRUD.load_data(event).get("amount") or 0))
    except TypeError, ValueError:
        return 0


def _revenue(payg: list[int], sales: list[int], days: int) -> PanelResellerRevenue:
    payg_total, sales_total = sum(payg[-days:]), sum(sales[-days:])
    return PanelResellerRevenue(payg=payg_total, sales=sales_total, total=payg_total + sales_total)


@router.post("/panel/resellers/overview", response_model=PanelResellerOverviewResponse)
async def reseller_overview(payload: PanelRequest, request: Request) -> PanelResellerOverviewResponse:
    async def handle(_: PanelActor) -> PanelResellerOverviewResponse:
        now = int(time.time())
        settings = await SettingsManager().get_settings()
        response = PanelResellerOverviewResponse(sale_enabled=bool(getattr(settings, "reseller_sale_mode", False)))

        for status, mode, count in await queries.reseller_breakdown():
            response.total += count
            response.by_status[status] = response.by_status.get(status, 0) + count
            response.by_mode[mode] = response.by_mode.get(mode, 0) + count

        boundaries = payment_stats.tehran_day_boundaries(REVENUE_DAYS)
        payg = await queries.reseller_billed_buckets(boundaries)
        sales = [0] * REVENUE_DAYS
        for event in await queries.reseller_events_between(boundaries[0], boundaries[-1], SALE_EVENT_KINDS):
            sales[bisect_right(boundaries, int(event.created_at)) - 1] += _event_amount(event)
        response.revenue_today = _revenue(payg, sales, 1)
        response.revenue_7d = _revenue(payg, sales, 7)
        response.revenue_30d = _revenue(payg, sales, REVENUE_DAYS)
        response.series = [
            PanelResellerDayPoint(ts=boundaries[index], payg=payg[index], sales=sales[index])
            for index in range(REVENUE_DAYS - SERIES_DAYS, REVENUE_DAYS)
        ]

        burning = await queries.burning_resellers(BURNING_MODES)
        balances = await queries.user_balances(sorted({account.telegram_id for account in burning}))
        runways = await estimate_runways(burning, balances)
        response.burn_per_hour = round(sum(runway.burn_per_hour for runway in runways.values()))
        warn_hours = int(getattr(settings, "reseller_low_balance_hours", 6) or 6)
        response.low_runway_hours = max(AT_RISK_MIN_HOURS, warn_hours)
        usernames: dict[int, list[str]] = {}
        for account in burning:
            usernames.setdefault(account.telegram_id, []).append(account.username)
        at_risk = [
            PanelResellerRunwayRow(
                telegram_id=telegram_id,
                balance=runway.balance,
                burn_per_hour=round(runway.burn_per_hour),
                hours_left=round(runway.hours_left, 2),
                accounts=usernames.get(telegram_id, []),
            )
            for telegram_id, runway in runways.items()
            if runway.hours_left is not None and runway.hours_left < response.low_runway_hours
        ]
        response.at_risk = sorted(at_risk, key=lambda row: row.hours_left or 0)[:AT_RISK_LIMIT]

        grace = grace_seconds(settings)
        expiring = await queries.resellers_expiring(now + EXPIRING_WINDOW, EXPIRABLE_STATUSES)
        expired = await queries.resellers_expiring(now + grace, ("expired",))
        response.expiring = sorted(
            [
                PanelResellerExpiringRow(
                    code=int(account.code),
                    telegram_id=account.telegram_id,
                    username=account.username,
                    status=account.status,
                    expiration_time=int(account.expiration_time),
                    purge_at=int(account.expiration_time) + grace if account.status == "expired" else None,
                )
                for account in [*expiring, *expired]
            ],
            key=lambda row: row.purge_at or row.expiration_time,
        )

        events, _ = await ResellerEventCRUD().list_events(limit=12)
        response.recent_events = [event_row(event) for event in events]
        return response

    return await guard.run(payload, request, PanelResellerOverviewResponse, handle)


@router.post("/panel/resellers/ledger", response_model=PanelResellerLedgerResponse)
async def reseller_ledger(payload: PanelResellerLedgerRequest, request: Request) -> PanelResellerLedgerResponse:
    async def handle(_: PanelActor) -> PanelResellerLedgerResponse:
        rows, total, billed = await queries.reseller_ledger(
            account_code=payload.account_code,
            telegram_id=payload.telegram_id,
            since=payload.since,
            until=payload.until,
            page=payload.page,
            per_page=payload.limit,
        )
        return PanelResellerLedgerResponse(
            rows=[snapshot_row(snapshot, account) for snapshot, account in rows],
            total_billed=billed,
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelResellerLedgerResponse, handle)


@router.post("/panel/resellers/events", response_model=PanelResellerEventsResponse)
async def reseller_events(payload: PanelResellerEventsRequest, request: Request) -> PanelResellerEventsResponse:
    async def handle(_: PanelActor) -> PanelResellerEventsResponse:
        kinds = tuple(kind for kind in payload.kinds if kind in EVENT_KINDS) or None
        events, total = await ResellerEventCRUD().list_events(
            account_code=payload.account_code,
            telegram_id=payload.telegram_id,
            kinds=kinds,
            limit=payload.limit,
            offset=(payload.page - 1) * payload.limit,
        )
        return PanelResellerEventsResponse(
            events=[event_row(event) for event in events],
            kinds=list(EVENT_KINDS),
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelResellerEventsResponse, handle)

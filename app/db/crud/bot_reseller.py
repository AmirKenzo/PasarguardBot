"""Data access for bot resellers (services, resellers, grants, their users and hourly usage)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.base import AsyncSessionLocal as Session
from app.db.models.bot_reseller import (
    GRANT_APPROVED,
    GRANT_PENDING,
    GRANT_REJECTED,
    GRANT_REVOKED,
    RESELLER_ACTIVE,
    BotReseller,
    BotResellerGrant,
    BotResellerService,
    BotResellerUsageHourly,
    BotResellerUser,
)
from app.db.models.user import User
from app.logger import get_logger
from app.utils.formatting.conversions import gigabytes_to_bytes

log = get_logger(__name__)

GB = gigabytes_to_bytes(1)


def _now() -> int:
    return int(time.time())


def _hour(ts: int) -> int:
    return int(ts) - int(ts) % 3600


def load_group_ids(raw: str | None) -> list[int]:
    try:
        return [int(x) for x in json.loads(raw or "[]")]
    except TypeError, ValueError:
        return []


def usage_delta(counter: int, baseline: int) -> int:
    """Bytes since the last charge; a counter that went back (usage reset) counts from zero."""
    counter = max(0, int(counter))
    baseline = max(0, int(baseline))
    return counter if counter < baseline else counter - baseline


@dataclass
class UsageResult:
    ok: bool
    charged: int = 0
    balance: int = 0
    bytes: int = 0
    by_service: dict[int, int] = field(default_factory=dict)


class BotResellerCRUD:
    async def list_services(
        self, *, panel_code: int | None = None, sale_only: bool = False
    ) -> list[BotResellerService]:
        stmt = select(BotResellerService).order_by(BotResellerService.id)
        if panel_code is not None:
            stmt = stmt.where(BotResellerService.panel_code == panel_code)
        if sale_only:
            stmt = stmt.where(BotResellerService.sale_enabled.is_(True))
        async with Session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def has_sale_services(self) -> bool:
        async with Session() as session:
            stmt = select(BotResellerService.id).where(BotResellerService.sale_enabled.is_(True)).limit(1)
            return (await session.execute(stmt)).first() is not None

    async def get_service(self, service_id: int) -> BotResellerService | None:
        async with Session() as session:
            return await session.get(BotResellerService, int(service_id))

    async def get_services(self, ids: Iterable[int]) -> dict[int, BotResellerService]:
        ids = {int(i) for i in ids}
        if not ids:
            return {}
        async with Session() as session:
            rows = (await session.execute(select(BotResellerService).where(BotResellerService.id.in_(ids)))).scalars()
            return {row.id: row for row in rows}

    async def save_service(
        self, service_id: int | None, *, group_ids: list[int], **values
    ) -> BotResellerService | None:
        now = _now()
        async with Session() as session:
            try:
                if service_id:
                    row = await session.get(BotResellerService, int(service_id))
                    if row is None:
                        return None
                else:
                    row = BotResellerService(created_at=now)
                    session.add(row)
                for key, value in values.items():
                    setattr(row, key, value)
                row.group_ids = json.dumps(sorted({int(g) for g in group_ids}))
                row.updated_at = now
                await session.commit()
                return row
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller service save failed id=%s: %s", service_id, e)
                return None

    async def set_service_sale(self, service_id: int, enabled: bool) -> bool:
        async with Session() as session:
            try:
                result = await session.execute(
                    update(BotResellerService)
                    .where(BotResellerService.id == int(service_id))
                    .values(sale_enabled=bool(enabled), updated_at=_now())
                )
                await session.commit()
                return bool(result.rowcount)
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller service toggle failed id=%s: %s", service_id, e)
                return False

    async def get_reseller(self, reseller_id: int) -> BotReseller | None:
        async with Session() as session:
            return await session.get(BotReseller, int(reseller_id))

    async def get_reseller_by_user(self, telegram_id: int) -> BotReseller | None:
        async with Session() as session:
            stmt = select(BotReseller).where(BotReseller.telegram_id == int(telegram_id))
            return (await session.execute(stmt)).scalars().first()

    async def ensure_reseller(self, telegram_id: int) -> BotReseller | None:
        existing = await self.get_reseller_by_user(telegram_id)
        if existing is not None:
            return existing
        async with Session() as session:
            try:
                row = BotReseller(
                    telegram_id=int(telegram_id), status=RESELLER_ACTIVE, username_prefix="", created_at=_now()
                )
                session.add(row)
                await session.flush()
                row.username_prefix = f"rb{row.id}"
                await session.commit()
                return row
            except IntegrityError:
                await session.rollback()
                return await self.get_reseller_by_user(telegram_id)
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller create failed user=%s: %s", telegram_id, e)
                return None

    async def update_reseller(self, reseller_id: int, **values) -> bool:
        async with Session() as session:
            try:
                await session.execute(update(BotReseller).where(BotReseller.id == int(reseller_id)).values(**values))
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller update failed id=%s: %s", reseller_id, e)
                return False

    async def list_resellers(self, *, ids: Iterable[int] | None = None) -> list[BotReseller]:
        stmt = select(BotReseller).order_by(BotReseller.id.desc())
        if ids is not None:
            stmt = stmt.where(BotReseller.id.in_({int(i) for i in ids}))
        async with Session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def balances(self, telegram_ids: Iterable[int]) -> dict[int, int]:
        ids = {int(i) for i in telegram_ids}
        if not ids:
            return {}
        async with Session() as session:
            rows = await session.execute(select(User.id, User.amount).where(User.id.in_(ids)))
            return {int(uid): int(amount or 0) for uid, amount in rows.all()}

    async def get_grant(self, grant_id: int) -> BotResellerGrant | None:
        async with Session() as session:
            return await session.get(BotResellerGrant, int(grant_id))

    async def has_approved_grant(self, telegram_id: int) -> bool:
        """Cheap check for menus: is this user a bot reseller with at least one active service."""
        async with Session() as session:
            stmt = (
                select(BotResellerGrant.id)
                .join(BotReseller, BotReseller.id == BotResellerGrant.reseller_id)
                .where(BotReseller.telegram_id == int(telegram_id), BotResellerGrant.status == GRANT_APPROVED)
                .limit(1)
            )
            return (await session.execute(stmt)).first() is not None

    async def find_grant(self, reseller_id: int, service_id: int) -> BotResellerGrant | None:
        async with Session() as session:
            stmt = select(BotResellerGrant).where(
                BotResellerGrant.reseller_id == int(reseller_id), BotResellerGrant.service_id == int(service_id)
            )
            return (await session.execute(stmt)).scalars().first()

    async def list_grants(
        self, *, reseller_id: int | None = None, status: str | None = None, statuses: Iterable[str] | None = None
    ) -> list[BotResellerGrant]:
        stmt = select(BotResellerGrant).order_by(BotResellerGrant.requested_at.desc())
        if reseller_id is not None:
            stmt = stmt.where(BotResellerGrant.reseller_id == int(reseller_id))
        if status:
            stmt = stmt.where(BotResellerGrant.status == status)
        if statuses is not None:
            stmt = stmt.where(BotResellerGrant.status.in_(list(statuses)))
        async with Session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def count_grants(self, status: str) -> int:
        async with Session() as session:
            stmt = select(func.count()).select_from(BotResellerGrant).where(BotResellerGrant.status == status)
            return int((await session.execute(stmt)).scalar() or 0)

    async def request_grant(self, reseller_id: int, service_id: int) -> tuple[BotResellerGrant | None, str | None]:
        """Open (or reopen after a rejection or revoke) a request; ``str`` is why it was refused."""
        async with Session() as session:
            try:
                stmt = select(BotResellerGrant).where(
                    BotResellerGrant.reseller_id == int(reseller_id), BotResellerGrant.service_id == int(service_id)
                )
                row = (await session.execute(stmt)).scalars().first()
                if row is not None and row.status in (GRANT_PENDING, GRANT_APPROVED):
                    return row, row.status
                if row is None:
                    row = BotResellerGrant(reseller_id=int(reseller_id), service_id=int(service_id))
                    session.add(row)
                row.status = GRANT_PENDING
                row.reject_reason = None
                row.requested_at = _now()
                row.decided_at = None
                row.decided_by = None
                await session.commit()
                return row, None
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller grant request failed reseller=%s service=%s: %s", reseller_id, service_id, e)
                return None, "error"

    async def decide_grant(
        self, grant_id: int, *, status: str, actor_id: int | None, **values
    ) -> BotResellerGrant | None:
        if status not in (GRANT_APPROVED, GRANT_REJECTED, GRANT_REVOKED):
            raise ValueError(status)
        async with Session() as session:
            try:
                row = await session.get(BotResellerGrant, int(grant_id))
                if row is None:
                    return None
                row.status = status
                row.decided_at = _now()
                row.decided_by = actor_id
                for key, value in values.items():
                    setattr(row, key, value)
                await session.commit()
                return row
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller grant decide failed id=%s: %s", grant_id, e)
                return None

    async def update_grant(self, grant_id: int, **values) -> bool:
        async with Session() as session:
            try:
                await session.execute(
                    update(BotResellerGrant).where(BotResellerGrant.id == int(grant_id)).values(**values)
                )
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller grant update failed id=%s: %s", grant_id, e)
                return False

    async def add_user(self, **values) -> BotResellerUser | None:
        async with Session() as session:
            try:
                row = BotResellerUser(created_at=_now(), **values)
                session.add(row)
                await session.commit()
                return row
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller user insert failed: %s", e)
                return None

    async def get_user(self, user_row_id: int) -> BotResellerUser | None:
        async with Session() as session:
            return await session.get(BotResellerUser, int(user_row_id))

    async def list_users(self, reseller_id: int, *, service_id: int | None = None) -> list[BotResellerUser]:
        stmt = (
            select(BotResellerUser)
            .where(BotResellerUser.reseller_id == int(reseller_id), BotResellerUser.deleted_at.is_(None))
            .order_by(BotResellerUser.id.desc())
        )
        if service_id is not None:
            stmt = stmt.where(BotResellerUser.service_id == int(service_id))
        async with Session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def live_users(self) -> list[BotResellerUser]:
        """Every user that still exists, for the billing run."""
        async with Session() as session:
            stmt = select(BotResellerUser).where(BotResellerUser.deleted_at.is_(None))
            return list((await session.execute(stmt)).scalars().all())

    async def count_users(self, reseller_id: int) -> dict[int, int]:
        """Live users per service of one reseller."""
        async with Session() as session:
            stmt = (
                select(BotResellerUser.service_id, func.count())
                .where(BotResellerUser.reseller_id == int(reseller_id), BotResellerUser.deleted_at.is_(None))
                .group_by(BotResellerUser.service_id)
            )
            return {int(sid): int(n) for sid, n in (await session.execute(stmt)).all()}

    async def count_all_users(self) -> dict[int, int]:
        async with Session() as session:
            stmt = (
                select(BotResellerUser.reseller_id, func.count())
                .where(BotResellerUser.deleted_at.is_(None))
                .group_by(BotResellerUser.reseller_id)
            )
            return {int(rid): int(n) for rid, n in (await session.execute(stmt)).all()}

    async def update_user(self, user_row_id: int, **values) -> bool:
        async with Session() as session:
            try:
                await session.execute(
                    update(BotResellerUser).where(BotResellerUser.id == int(user_row_id)).values(**values)
                )
                await session.commit()
                return True
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("bot reseller user update failed id=%s: %s", user_row_id, e)
                return False

    async def set_disabled_by(self, user_row_ids: Iterable[int], value: str | None) -> None:
        ids = [int(i) for i in user_row_ids]
        if not ids:
            return
        async with Session() as session:
            await session.execute(update(BotResellerUser).where(BotResellerUser.id.in_(ids)).values(disabled_by=value))
            await session.commit()

    async def apply_usage(
        self, reseller_id: int, counters: dict[int, int], prices: dict[int, float], *, now: int | None = None
    ) -> UsageResult:
        """Charge the traffic of ``counters`` (user row id -> panel counter) in one transaction.

        The wallet debit, the carried remainder, every user's baseline and the hourly rows move
        together; the baselines are read inside the transaction, so two runs can never bill the
        same bytes. The wallet may go negative by at most one run of traffic.
        """
        now = int(now or _now())
        if not counters:
            return UsageResult(ok=True)
        try:
            async with Session() as session:
                dialect = session.bind.dialect if session.bind is not None else None
                lock = bool(dialect and dialect.name != "sqlite")

                stmt = select(BotReseller).where(BotReseller.id == int(reseller_id))
                reseller = (await session.execute(stmt.with_for_update() if lock else stmt)).scalars().first()
                if reseller is None:
                    return UsageResult(ok=False)
                stmt = select(User).where(User.id == reseller.telegram_id)
                wallet = (await session.execute(stmt.with_for_update() if lock else stmt)).scalars().first()
                if wallet is None:
                    return UsageResult(ok=False)

                stmt = select(BotResellerUser).where(
                    BotResellerUser.reseller_id == reseller.id, BotResellerUser.id.in_(list(counters))
                )
                users = (await session.execute(stmt.with_for_update() if lock else stmt)).scalars().all()

                exact_by_service: dict[int, float] = {}
                bytes_by_service: dict[int, int] = {}
                for user in users:
                    counter = int(counters[user.id])
                    delta = usage_delta(counter, user.baseline_bytes)
                    user.baseline_bytes = counter
                    if delta <= 0:
                        continue
                    price = float(prices.get(user.service_id) or 0)
                    exact_by_service[user.service_id] = exact_by_service.get(user.service_id, 0.0) + delta / GB * price
                    bytes_by_service[user.service_id] = bytes_by_service.get(user.service_id, 0) + delta

                exact = sum(exact_by_service.values()) + float(reseller.carry or 0)
                charge = int(exact)
                reseller.carry = round(exact - charge, 6)
                balance = int(wallet.amount or 0) - charge
                wallet.amount = balance

                hour = _hour(now)
                for service_id, used in bytes_by_service.items():
                    stmt = select(BotResellerUsageHourly).where(
                        BotResellerUsageHourly.reseller_id == reseller.id,
                        BotResellerUsageHourly.service_id == service_id,
                        BotResellerUsageHourly.hour == hour,
                    )
                    row = (await session.execute(stmt)).scalars().first()
                    if row is None:
                        row = BotResellerUsageHourly(
                            reseller_id=reseller.id, service_id=service_id, hour=hour, bytes=0, amount=0
                        )
                        session.add(row)
                    row.bytes = int(row.bytes or 0) + used
                    row.amount = round(float(row.amount or 0) + exact_by_service[service_id], 6)

                await session.commit()
                return UsageResult(
                    ok=True,
                    charged=charge,
                    balance=balance,
                    bytes=sum(bytes_by_service.values()),
                    by_service=bytes_by_service,
                )
        except SQLAlchemyError as e:
            log.error("bot reseller usage charge failed reseller=%s: %s", reseller_id, e)
            return UsageResult(ok=False)

    async def usage_rows(self, reseller_id: int, *, since: int, service_id: int | None = None) -> list:
        stmt = (
            select(BotResellerUsageHourly)
            .where(BotResellerUsageHourly.reseller_id == int(reseller_id), BotResellerUsageHourly.hour >= int(since))
            .order_by(BotResellerUsageHourly.hour.desc())
        )
        if service_id is not None:
            stmt = stmt.where(BotResellerUsageHourly.service_id == int(service_id))
        async with Session() as session:
            return list((await session.execute(stmt)).scalars().all())

    async def usage_totals(self, *, since: int, reseller_id: int | None = None) -> dict[int, tuple[int, float]]:
        """(bytes, amount) per reseller since ``since``."""
        stmt = (
            select(
                BotResellerUsageHourly.reseller_id,
                func.sum(BotResellerUsageHourly.bytes),
                func.sum(BotResellerUsageHourly.amount),
            )
            .where(BotResellerUsageHourly.hour >= int(since))
            .group_by(BotResellerUsageHourly.reseller_id)
        )
        if reseller_id is not None:
            stmt = stmt.where(BotResellerUsageHourly.reseller_id == int(reseller_id))
        async with Session() as session:
            return {int(rid): (int(b or 0), float(a or 0)) for rid, b, a in (await session.execute(stmt)).all()}

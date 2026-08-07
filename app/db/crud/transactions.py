import time

from sqlalchemy import case, func
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.settings import SettingsManager
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.services.billing.payment_bonus import calculate_payment_bonus


def _tx_processed_at():
    """When completed_at is missing (e.g. legacy auto SMS approvals), fall back to created_at."""
    return func.coalesce(Transaction.completed_at, Transaction.created_at)


def _distinct_user_count_stmt():
    return select(func.count(func.distinct(Transaction.user_id))).where(Transaction.status == "approved")


class TransactionCRUD:
    async def create(
        self,
        user_id: int,
        amount: int,
        method: str,
        status: str = "pending",
        message_id: int | None = None,
        message_chat_id: int | None = None,
    ):
        async with Session() as session:
            now = int(__import__("time").time())
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                method=method,
                status=status,
                created_at=now,
                completed_at=now if status in ("approved", "rejected") else None,
                message_id=message_id,
                message_chat_id=message_chat_id,
            )
            session.add(transaction)
            await session.commit()
            return transaction

    async def get(self, tx_id: int):
        async with Session() as session:
            result = await session.execute(select(Transaction).filter_by(id=tx_id))
            return result.scalar_one_or_none()

    async def update(self, tx_id: int, **kwargs):
        async with Session() as session:
            result = await session.execute(select(Transaction).filter_by(id=tx_id))
            tx = result.scalar_one_or_none()
            if tx:
                for key, value in kwargs.items():
                    if hasattr(tx, key):
                        setattr(tx, key, value)
                await session.commit()
                return tx
            return None

    async def get_pending_manual(self):
        async with Session() as session:
            result = await session.execute(
                select(Transaction).where(Transaction.method == "manual", Transaction.status == "pending")
            )
            return result.scalars().all()

    async def approve_manual(self, tx: Transaction) -> dict | None:
        """Approve pending manual tx with bonus. Returns None if not pending."""
        tx_id = int(tx.id)
        if tx.status != "pending":
            return None
        settings = await SettingsManager().get_settings()
        bonus = await calculate_payment_bonus(
            amount=int(tx.amount),
            bonus_enabled=settings.manual_bonus_enabled,
            bonus_percent=settings.manual_bonus_percent,
        )
        total = int(tx.amount) + bonus
        now = int(time.time())
        async with Session() as session, session.begin():
            tx_stmt = select(Transaction).where(Transaction.id == tx_id)
            user_stmt = select(User).where(User.id == tx.user_id)
            dialect = session.bind.dialect if session.bind is not None else None
            if dialect and dialect.name != "sqlite":
                tx_stmt = tx_stmt.with_for_update()
                user_stmt = user_stmt.with_for_update()

            result = await session.execute(tx_stmt)
            locked_tx = result.scalar_one_or_none()
            if not locked_tx or locked_tx.status != "pending":
                return None

            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                return None

            user.amount = int(user.amount or 0) + total
            locked_tx.status = "approved"
            locked_tx.completed_at = now
            locked_tx.auto_approve_at = None
            locked_tx.auto_approve_rule_id = None
            new_balance = int(user.amount or 0)
        return {"new_balance": int(new_balance), "bonus": bonus, "total": total, "completed_at": now}

    async def get_pending_manual_due_auto_approve(self, now: int):
        """Pending manual transactions whose auto_approve_at has passed."""
        async with Session() as session:
            result = await session.execute(
                select(Transaction).where(
                    Transaction.method == "manual",
                    Transaction.status == "pending",
                    Transaction.auto_approve_at.isnot(None),
                    Transaction.auto_approve_at <= now,
                )
            )
            return result.scalars().all()

    async def count_transactions(self, status: str | None = None, method: str | None = None) -> int:
        async with Session() as session:
            stmt = select(func.count()).select_from(Transaction)
            if status:
                stmt = stmt.where(Transaction.status == status)
            if method:
                stmt = stmt.where(Transaction.method == method)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def count_user_transactions(self, user_id: int, status: str | None = None, method: str | None = None) -> int:
        async with Session() as session:
            stmt = select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
            if status:
                stmt = stmt.where(Transaction.status == status)
            if method:
                stmt = stmt.where(Transaction.method == method)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def count_user_transactions_by_method_status(self, user_id: int) -> dict[tuple[str | None, str | None], int]:
        """Single GROUP BY method,status for a user's transactions."""
        async with Session() as session:
            stmt = (
                select(Transaction.method, Transaction.status, func.count())
                .where(Transaction.user_id == user_id)
                .group_by(Transaction.method, Transaction.status)
            )
            result = await session.execute(stmt)
            return {(method, status): int(count or 0) for method, status, count in result.all()}

    async def sum_transactions(
        self,
        start: int | None = None,
        end: int | None = None,
        status: str = "approved",
    ) -> int:
        async with Session() as session:
            stmt = select(func.sum(Transaction.amount)).where(Transaction.status == status)
            if start is not None:
                stmt = stmt.where(Transaction.created_at >= start)
            if end is not None:
                stmt = stmt.where(Transaction.created_at < end)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_sales_total(self) -> int:
        """All-time approved transaction revenue only."""
        async with Session() as session:
            stmt = select(func.sum(Transaction.amount)).where(Transaction.status == "approved")
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def get_dashboard_sales(self, ts: dict) -> dict:
        """Sales buckets for main dashboard (no all-time total)."""
        async with Session() as session:
            approved = Transaction.status == "approved"
            today_ts = ts["today_ts"]
            yesterday_ts = ts["yesterday_ts"]
            day_2_ts = ts["two_days_ago_ts"]
            day_3_ts = ts["three_days_ago_ts"]
            week_ts = ts["week_ts"]
            stmt = select(
                func.sum(case(((approved) & (Transaction.created_at >= today_ts), Transaction.amount), else_=0)).label(
                    "sales_today"
                ),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= yesterday_ts) & (Transaction.created_at < today_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_yesterday"),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= day_2_ts) & (Transaction.created_at < yesterday_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_2d_ago"),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= day_3_ts) & (Transaction.created_at < day_2_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_3d_ago"),
                func.sum(case(((approved) & (Transaction.created_at >= week_ts), Transaction.amount), else_=0)).label(
                    "sales_7d"
                ),
            ).select_from(Transaction)
            row = (await session.execute(stmt)).one()
            return {
                "sales_today": int(row.sales_today or 0),
                "sales_yesterday": int(row.sales_yesterday or 0),
                "sales_2d_ago": int(row.sales_2d_ago or 0),
                "sales_3d_ago": int(row.sales_3d_ago or 0),
                "sales_7d": int(row.sales_7d or 0),
            }

    async def get_pending_manual_summary(self) -> dict:
        """Current pending manual card-to-card queue."""
        async with Session() as session:
            stmt = select(
                func.count().label("count"),
                func.sum(Transaction.amount).label("amount"),
            ).where(Transaction.method == "manual", Transaction.status == "pending")
            row = (await session.execute(stmt)).one()
            return {"count": int(row.count or 0), "amount": int(row.amount or 0)}

    async def get_sales_summary(self, today_ts: int, yesterday_ts: int) -> dict:
        """Lightweight today / yesterday / total sales."""
        async with Session() as session:
            approved = Transaction.status == "approved"
            stmt = select(
                func.sum(case((approved, Transaction.amount), else_=0)).label("sales_total"),
                func.sum(case(((approved) & (Transaction.created_at >= today_ts), Transaction.amount), else_=0)).label(
                    "sales_today"
                ),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= yesterday_ts) & (Transaction.created_at < today_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_yesterday"),
            ).select_from(Transaction)
            row = (await session.execute(stmt)).one()
            return {
                "sales_total": int(row.sales_total or 0),
                "sales_today": int(row.sales_today or 0),
                "sales_yesterday": int(row.sales_yesterday or 0),
            }

    async def get_breakdown(self, start_ts: int, end_ts: int | None = None) -> dict:
        """Counts and amounts by method/status in a time window.

        Approved/rejected use processed time (completed_at or created_at fallback).
        Pending uses created_at (submissions still waiting).
        """
        async with Session() as session:
            processed_at = _tx_processed_at()
            cols = []
            specs = [
                ("manual", "approved", processed_at),
                ("manual", "rejected", processed_at),
                ("manual", "pending", Transaction.created_at),
                ("auto", "approved", processed_at),
                ("auto", "rejected", processed_at),
                ("auto", "pending", Transaction.created_at),
            ]
            for method, status, time_col in specs:
                cond = (Transaction.method == method) & (Transaction.status == status)
                cond = cond & (time_col >= start_ts)
                if end_ts is not None:
                    cond = cond & (time_col < end_ts)
                key = f"{method}_{status}"
                cols.append(func.sum(case((cond, 1), else_=0)).label(f"{key}_count"))
                cols.append(func.sum(case((cond, Transaction.amount), else_=0)).label(f"{key}_sum"))

            pending_manual = Transaction.method == "manual"
            pending_manual = pending_manual & (Transaction.status == "pending")
            cols.append(func.sum(case((pending_manual, 1), else_=0)).label("manual_pending_total_count"))
            cols.append(func.sum(case((pending_manual, Transaction.amount), else_=0)).label("manual_pending_total_sum"))

            row = (await session.execute(select(*cols).select_from(Transaction))).one()
            out: dict = {}
            for method, status, _ in specs:
                key = f"{method}_{status}"
                out[f"{key}_count"] = int(getattr(row, f"{key}_count") or 0)
                out[f"{key}_sum"] = int(getattr(row, f"{key}_sum") or 0)
            out["manual_pending_total_count"] = int(row.manual_pending_total_count or 0)
            out["manual_pending_total_sum"] = int(row.manual_pending_total_sum or 0)
            return out

    async def get_top_recharge_today(self, today_ts: int, limit: int = 5) -> list[tuple[int, int, int]]:
        """(user_id, tx_count, total_amount) for top rechargers today."""
        async with Session() as session:
            stmt = (
                select(
                    Transaction.user_id,
                    func.count().label("cnt"),
                    func.sum(Transaction.amount).label("total"),
                )
                .where(
                    Transaction.status == "approved",
                    _tx_processed_at() >= today_ts,
                )
                .group_by(Transaction.user_id)
                .order_by(func.count().desc(), func.sum(Transaction.amount).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [(r.user_id, int(r.cnt or 0), int(r.total or 0)) for r in result.all()]

    async def get_top_spenders_today(self, today_ts: int, limit: int = 5) -> list[tuple[int, int, int]]:
        """(user_id, total_amount, tx_count) for top spenders today."""
        async with Session() as session:
            stmt = (
                select(
                    Transaction.user_id,
                    func.sum(Transaction.amount).label("total"),
                    func.count().label("cnt"),
                )
                .where(
                    Transaction.status == "approved",
                    _tx_processed_at() >= today_ts,
                )
                .group_by(Transaction.user_id)
                .order_by(func.sum(Transaction.amount).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [(r.user_id, int(r.total or 0), int(r.cnt or 0)) for r in result.all()]

    async def get_stats(
        self,
        today_ts: int,
        yesterday_ts: int,
        week_ts: int,
        month_ts: int,
        two_days_ago_ts: int | None = None,
        three_days_ago_ts: int | None = None,
    ) -> dict:
        async with Session() as session:
            approved = Transaction.status == "approved"
            cols = [
                func.sum(case(((approved) & (Transaction.method == "manual"), 1), else_=0)).label("manual_approved"),
                func.sum(case(((approved) & (Transaction.method == "auto"), 1), else_=0)).label("auto_approved"),
                func.sum(case((Transaction.status == "rejected", 1), else_=0)).label("rejected"),
                func.sum(case((approved, Transaction.amount), else_=0)).label("sales_total"),
                func.sum(case(((approved) & (Transaction.created_at >= today_ts), Transaction.amount), else_=0)).label(
                    "sales_today"
                ),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= yesterday_ts) & (Transaction.created_at < today_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_yesterday"),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= week_ts) & (Transaction.created_at < today_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_week"),
                func.sum(
                    case(
                        (
                            (approved) & (Transaction.created_at >= month_ts) & (Transaction.created_at < today_ts),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ).label("sales_month"),
            ]
            if two_days_ago_ts is not None and three_days_ago_ts is not None:
                cols.extend(
                    [
                        func.sum(
                            case(
                                (
                                    (approved)
                                    & (Transaction.created_at >= two_days_ago_ts)
                                    & (Transaction.created_at < yesterday_ts),
                                    Transaction.amount,
                                ),
                                else_=0,
                            )
                        ).label("sales_2_days_ago"),
                        func.sum(
                            case(
                                (
                                    (approved)
                                    & (Transaction.created_at >= three_days_ago_ts)
                                    & (Transaction.created_at < two_days_ago_ts),
                                    Transaction.amount,
                                ),
                                else_=0,
                            )
                        ).label("sales_3_days_ago"),
                    ]
                )
            result = await session.execute(select(*cols).select_from(Transaction))
            row = result.one()
            customers_result = await session.execute(_distinct_user_count_stmt())
            customers_count = customers_result.scalar() or 0
            return {
                "manual_approved": int(row.manual_approved or 0),
                "auto_approved": int(row.auto_approved or 0),
                "rejected": int(row.rejected or 0),
                "sales_total": int(row.sales_total or 0),
                "sales_today": int(row.sales_today or 0),
                "sales_yesterday": int(row.sales_yesterday or 0),
                "sales_week": int(row.sales_week or 0),
                "sales_month": int(row.sales_month or 0),
                "sales_2_days_ago": int(getattr(row, "sales_2_days_ago", 0) or 0),
                "sales_3_days_ago": int(getattr(row, "sales_3_days_ago", 0) or 0),
                "customers_count": int(customers_count),
            }

    async def get_user_transaction_stats(self, user_id: int, method: str) -> dict:
        async with Session() as session:
            count_stmt = (
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.user_id == user_id, Transaction.method == method, Transaction.status == "approved")
            )
            count_result = await session.execute(count_stmt)
            count = count_result.scalar() or 0

            sum_stmt = select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id, Transaction.method == method, Transaction.status == "approved"
            )
            sum_result = await session.execute(sum_stmt)
            total_amount = sum_result.scalar() or 0

            return {"count": count, "total_amount": total_amount}

    async def get_user_all_transactions(self, user_id: int):
        async with Session() as session:
            result = await session.execute(
                select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc())
            )
            return result.scalars().all()

    async def get_user_transaction_by_id(self, user_id: int, tx_id: int):
        async with Session() as session:
            result = await session.execute(
                select(Transaction).where(Transaction.user_id == user_id, Transaction.id == tx_id)
            )
            return result.scalar_one_or_none()

    async def get_top_customers_by_spend(self, limit: int = 10) -> list[tuple[int, int, int]]:
        """(user_id, total_amount, tx_count) ordered by total spend desc."""
        async with Session() as session:
            stmt = (
                select(
                    Transaction.user_id,
                    func.sum(Transaction.amount).label("total"),
                    func.count().label("cnt"),
                )
                .where(Transaction.status == "approved")
                .group_by(Transaction.user_id)
                .order_by(func.sum(Transaction.amount).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [(r.user_id, int(r.total or 0), int(r.cnt or 0)) for r in result.all()]

    async def get_top_customers_by_tx_count(self, limit: int = 10) -> list[tuple[int, int, int]]:
        """(user_id, tx_count, total_amount) ordered by tx count desc."""
        async with Session() as session:
            stmt = (
                select(
                    Transaction.user_id,
                    func.count().label("cnt"),
                    func.sum(Transaction.amount).label("total"),
                )
                .where(Transaction.status == "approved")
                .group_by(Transaction.user_id)
                .order_by(func.count().desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [(r.user_id, int(r.cnt or 0), int(r.total or 0)) for r in result.all()]

    async def get_most_spender_today(self, today_ts: int) -> tuple[int, int] | None:
        """(user_id, amount) for user with max spend today (by completed_at), or None."""
        async with Session() as session:
            sub = (
                select(
                    Transaction.user_id,
                    func.sum(Transaction.amount).label("total"),
                )
                .where(
                    Transaction.status == "approved",
                    _tx_processed_at() >= today_ts,
                )
                .group_by(Transaction.user_id)
                .order_by(func.sum(Transaction.amount).desc())
                .limit(1)
            )
            result = await session.execute(sub)
            row = result.one_or_none()
            if row and row.total:
                return (row.user_id, int(row.total))
            return None

    async def get_oldest_customer(self) -> tuple[int, int] | None:
        """(user_id, created_at) for first approved transaction, or None."""
        async with Session() as session:
            stmt = (
                select(Transaction.user_id, Transaction.created_at)
                .where(Transaction.status == "approved")
                .order_by(Transaction.created_at.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.one_or_none()
            return (row.user_id, row.created_at) if row else None

    async def get_newest_customer(self) -> tuple[int, int] | None:
        """(user_id, created_at) for latest approved transaction, or None."""
        async with Session() as session:
            stmt = (
                select(Transaction.user_id, Transaction.created_at)
                .where(Transaction.status == "approved")
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.one_or_none()
            return (row.user_id, row.created_at) if row else None

import re
import time

from sqlalchemy import and_, case, distinct, func, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.services import Service
from app.db.models.user import User
from app.logger import get_logger

log = get_logger(__name__)

# DB `user.status` — only inactive account flags; NULL = normal active user.
PERSISTENT_USER_STATUS_STEPS = frozenset({"ban", "BlockedBot", "DeleteAccount"})
INACTIVE_USER_STATUSES = tuple(PERSISTENT_USER_STATUS_STEPS)
LEGACY_STATUS_VALUES = frozenset({"home", "start", "none"})
CLEAR_ACCOUNT_STATUS_VALUES = frozenset({"none", "", "home", "start"})
AUTO_CLEAR_STATUSES = frozenset({"BlockedBot", "DeleteAccount"})

# Ban/status changes rarely; cache to avoid a SELECT on every non-admin update.
_STATUS_LOCAL_TTL_SEC = 30.0
_status_local: dict[int, tuple[float, str | None]] = {}


def _invalidate_status_local(user_id: int) -> None:
    _status_local.pop(user_id, None)


def _get_status_local(user_id: int) -> tuple[bool, str | None]:
    entry = _status_local.get(user_id)
    if entry is None:
        return False, None
    ts, value = entry
    if time.monotonic() - ts > _STATUS_LOCAL_TTL_SEC:
        _status_local.pop(user_id, None)
        return False, None
    return True, value


def _set_status_local(user_id: int, value: str | None) -> None:
    _status_local[user_id] = (time.monotonic(), value)
    if len(_status_local) > 20_000:
        now = time.monotonic()
        stale = [uid for uid, (t, _) in _status_local.items() if now - t > _STATUS_LOCAL_TTL_SEC]
        for uid in stale:
            _status_local.pop(uid, None)


def _user_has_active_status_expr():
    return or_(User.status.is_(None), User.status.notin_(INACTIVE_USER_STATUSES))


async def _read_db_status(user_id: int) -> str | None:
    async with Session() as session:
        result = await session.execute(select(User.status).filter_by(id=user_id))
        raw = result.scalar_one_or_none()
        if raw in LEGACY_STATUS_VALUES:
            return None
        return raw


async def set_user_status(
    user_id: int,
    status: str,
    *,
    time_s=None,
    language: str | None = None,
) -> None:
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            existing_user.status = status
            if language is not None:
                existing_user.language = language
        else:
            session.add(
                User(
                    id=user_id,
                    status=status,
                    time_s=time_s,
                    language=language or "fa",
                )
            )
        await session.commit()
    _invalidate_status_local(user_id)


async def clear_user_status(
    user_id: int,
    *,
    time_s=None,
    language: str | None = None,
) -> None:
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            existing_user.status = None
            if language is not None:
                existing_user.language = language
        else:
            session.add(
                User(
                    id=user_id,
                    status=None,
                    time_s=time_s,
                    language=language or "fa",
                )
            )
        await session.commit()
    _invalidate_status_local(user_id)


async def set_user_language(user_id: int, language: str) -> None:
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            existing_user.language = language
            await session.commit()


async def get_user_status(user_id: int) -> str | None:
    """Persistent account status in DB: `ban`, `BlockedBot`, `DeleteAccount`, or NULL."""
    hit, cached = _get_status_local(user_id)
    if hit:
        return cached
    status = await _read_db_status(user_id)
    _set_status_local(user_id, status)
    return status


async def clear_reactivatable_status(user_id: int) -> str | None:
    """Clear BlockedBot/DeleteAccount when user interacts with the bot again. Keeps `ban`."""
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()
        if not user or user.status not in AUTO_CLEAR_STATUSES:
            return None
        previous = user.status
        user.status = None
        await session.commit()
    _invalidate_status_local(user_id)
    return previous


class UserCRUD:
    async def create_user(
        self,
        id,
        step,
        ref=None,
        number=None,
        amount=None,
        invite=None,
        tested=False,
        page=None,
        language="fa",
    ):
        async with Session() as session:
            try:
                db_status = step if step in PERSISTENT_USER_STATUS_STEPS else None
                new_user = User(
                    id=id,
                    status=db_status,
                    ref=ref,
                    number=number,
                    amount=amount,
                    invite=invite,
                    tested=tested,
                    page=page,
                    language=language,
                )
                session.add(new_user)
                await session.commit()
                return new_user
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error creating user: %s", e)
                return None

    async def read_user(self, user_id):
        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            return result.scalars().first()

    async def update_user(self, user_id, **kwargs):
        language = kwargs.pop("language", None)
        kwargs.pop("step", None)  # conversation step — use Redis (`app.telegram.state`), not DB
        if language is not None:
            await set_user_language(user_id, language)

        if not kwargs:
            return language is not None

        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            existing_user = result.scalar()
            if existing_user:
                for key, value in kwargs.items():
                    setattr(existing_user, key, value)
                await session.commit()
                return True
            return False

    async def increment_invites(self, user_id):
        async with Session() as session:
            stmt = update(User).where(User.id == user_id).values(invite=func.coalesce(User.invite, 0) + 1)
            result = await session.execute(stmt)
            if result.rowcount:
                await session.commit()
                return True, "The number of invitations has been successfully increased."
            return False, "There is no user....."

    async def update_ref(self, user_id, ref_value):
        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            existing_user = result.scalar()
            if existing_user:
                if not existing_user.ref:
                    ref_result = await session.execute(select(User).filter_by(id=ref_value))
                    ref_user = ref_result.scalar()
                    if ref_user:
                        if str(ref_value) != str(user_id):
                            existing_user.ref = ref_value
                            await session.commit()
                            res, msg = await self.increment_invites(ref_value)
                            if res:
                                return res, msg
                            return False, "Invite Ezafe Nashod"
                        return False, "You cannot register yourself as a referral."
                    return False, "The referral user is not valid."
                return False, "The referral has already been registered."
            return False, "There is no user."

    async def get_referred_users(self, referrer_id):
        """Get all users referred by a specific user"""
        async with Session() as session:
            try:
                result = await session.execute(select(User).filter_by(ref=referrer_id))
                return result.scalars().all()
            except SQLAlchemyError as e:
                log.error("Error getting referred users: %s", e)
                return []

    async def delete_user(self, user_id):
        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalar_one_or_none()
            if user:
                try:
                    await session.delete(user)
                    await session.commit()
                    return True
                except SQLAlchemyError as e:
                    await session.rollback()
                    log.error("Error deleting user: %s", e)
                    return False
            return False

    async def get_all_users(self):
        async with Session() as session:
            result = await session.execute(select(User))
            return result.scalars().all()

    async def get_users_with_tested(self):
        """Get all users who have tested = True (have taken test config)"""
        async with Session() as session:
            result = await session.execute(select(User).filter_by(tested=True))
            return result.scalars().all()

    async def get_users_with_active_services(self):
        """Get all users who have at least one active service."""
        async with Session() as session:
            now = int(time.time())
            # Get distinct user IDs with active services
            subquery = (
                select(distinct(Service.id).label("user_id")).where(
                    and_(
                        Service.enable.is_(True),
                        Service.expiration_time.isnot(None),
                        Service.expiration_time > now,
                    )
                )
            ).subquery()

            # Join with User table
            query = select(User).join(subquery, User.id == subquery.c.user_id).order_by(User.id)
            result = await session.execute(query)
            users = result.scalars().all()
            return list(users)

    async def count_all_users(self) -> int:
        async with Session() as session:
            result = await session.execute(select(func.count()).select_from(User))
            return result.scalar() or 0

    async def get_overview_counts(self) -> dict:
        """Lightweight total + active user counts for stats overview."""
        async with Session() as session:
            stmt = select(
                func.count().label("total"),
                func.sum(case((_user_has_active_status_expr(), 1), else_=0)).label("active"),
            ).select_from(User)
            result = await session.execute(stmt)
            row = result.one()
            return {
                "total": int(row.total or 0),
                "active": int(row.active or 0),
            }

    async def get_blocked_stats(self) -> dict:
        """Banned, blocked-bot, and deleted-account counts only."""
        async with Session() as session:
            stmt = select(
                func.sum(case((User.status == "ban", 1), else_=0)).label("banned"),
                func.sum(case((User.status == "BlockedBot", 1), else_=0)).label("blocked"),
                func.sum(case((User.status == "DeleteAccount", 1), else_=0)).label("deleted"),
            ).select_from(User)
            result = await session.execute(stmt)
            row = result.one()
            banned = int(row.banned or 0)
            blocked = int(row.blocked or 0)
            deleted = int(row.deleted or 0)
            return {
                "banned": banned,
                "blocked": blocked,
                "deleted": deleted,
                "inactive_total": banned + blocked + deleted,
            }

    async def get_user_stats(
        self,
        month_ts: int,
        week_ts: int,
        day_ts: int,
        day_2_ts: int | None = None,
        day_3_ts: int | None = None,
        day_4_ts: int | None = None,
        today_ts: int | None = None,
    ) -> dict:
        async with Session() as session:
            cols = [
                func.count().label("total"),
                func.sum(case((User.status == "ban", 1), else_=0)).label("banned"),
                func.sum(case((User.status == "BlockedBot", 1), else_=0)).label("blocked"),
                func.sum(case((User.status == "DeleteAccount", 1), else_=0)).label("deleted"),
                func.sum(case((_user_has_active_status_expr(), 1), else_=0)).label("active"),
                func.sum(case((User.time_s >= month_ts, 1), else_=0)).label("members_month"),
                func.sum(case((User.time_s >= week_ts, 1), else_=0)).label("members_week"),
                func.sum(case((User.time_s >= day_ts, 1), else_=0)).label("members_day"),
            ]
            if today_ts is not None:
                cols.append(func.sum(case((User.time_s >= today_ts, 1), else_=0)).label("members_today"))
            if day_2_ts is not None and day_3_ts is not None and day_4_ts is not None:
                cols.extend(
                    [
                        func.sum(case((and_(User.time_s >= day_2_ts, User.time_s < day_ts), 1), else_=0)).label(
                            "members_1d_ago"
                        ),
                        func.sum(case((and_(User.time_s >= day_3_ts, User.time_s < day_2_ts), 1), else_=0)).label(
                            "members_2d_ago"
                        ),
                        func.sum(case((and_(User.time_s >= day_4_ts, User.time_s < day_3_ts), 1), else_=0)).label(
                            "members_3d_ago"
                        ),
                    ]
                )
            stmt = select(*cols).select_from(User)
            result = await session.execute(stmt)
            row = result.one()
            return {
                "total": int(row.total or 0),
                "banned": int(row.banned or 0),
                "blocked": int(row.blocked or 0),
                "deleted": int(row.deleted or 0),
                "active": int(row.active or 0),
                "members_month": int(row.members_month or 0),
                "members_week": int(row.members_week or 0),
                "members_day": int(row.members_day or 0),
                "members_1d_ago": int(getattr(row, "members_1d_ago", 0) or 0),
                "members_2d_ago": int(getattr(row, "members_2d_ago", 0) or 0),
                "members_3d_ago": int(getattr(row, "members_3d_ago", 0) or 0),
                "members_today": int(getattr(row, "members_today", 0) or 0),
            }

    async def Add_Money(self, user_id, Money):
        return await update_Money(user_id, Money)

    async def all_users_block(self):
        async with Session() as session:
            result_blocked = await session.execute(select(func.count()).filter(User.status == "BlockedBot"))
            blocked_count = result_blocked.scalar()
            result_deleted = await session.execute(select(func.count()).filter(User.status == "DeleteAccount"))
            deleted_count = result_deleted.scalar()
            return blocked_count, deleted_count

    async def all_users_active(self):
        async with Session() as session:
            result = await session.execute(select(func.count()).filter(_user_has_active_status_expr()))
            return result.scalar()

    async def count_since(self, timestamp: int) -> int:
        async with Session() as session:
            result = await session.execute(select(func.count()).select_from(User).where(User.time_s >= timestamp))
            return result.scalar() or 0

    async def get_user_by_phone(self, phone: str):
        """Find user by phone number with basic normalization.

        Tries common formats like 09XXXXXXXXX, +989XXXXXXXXX, 989XXXXXXXXX.
        Returns the first matching user or None.
        """
        # Keep only digits
        digits = re.sub(r"\D+", "", phone or "")
        candidates = []
        if not digits:
            return None

        # As-is
        candidates.append(digits)

        # 09xxxxxxxxx
        if digits.startswith("98") and len(digits) >= 12:
            candidates.append("0" + digits[2:])
        elif digits.startswith("9") and len(digits) == 10:
            candidates.append("0" + digits)

        # +98xxxxxxxxxx and 98xxxxxxxxxx
        if digits.startswith("0") and len(digits) >= 11:
            candidates.append("98" + digits[1:])
        if not digits.startswith("98") and len(digits) >= 10:
            candidates.append("98" + digits)

        # With plus variant
        candidates += ["+" + c for c in list(candidates)]

        # Deduplicate while preserving order
        seen = set()
        norm_candidates = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                norm_candidates.append(c)

        async with Session() as session:
            for cand in norm_candidates:
                result = await session.execute(select(User).filter_by(number=cand))
                user = result.scalars().first()
                if user:
                    return user
        return None


class UserManager:
    def __init__(self):
        self.session = Session()

    async def get_user_by_id(self, user_id: int):
        async with Session() as session:
            existing_user = await session.execute(select(User).filter_by(id=user_id))
            return existing_user.scalars().first()

    async def update_user_balance(self, user_id: int, amount: float):
        new_balance = await update_Money(user_id, amount)
        if new_balance is None:
            return None
        return await self.get_user_by_id(user_id)

    async def create_user(self, user_id: int, initial_amount: int = 0):
        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if not user:
                new_user = User(id=user_id, amount=initial_amount, status=None)
                session.add(new_user)
                await session.commit()
                return new_user
            return user

    async def update_user_phone_number(self, user_id: int, phone_number: str):
        async with Session() as session:
            result = await session.execute(select(User).filter_by(id=user_id))
            user = result.scalars().first()
            if user:
                user.number = phone_number
                await session.commit()
                return True
            return False


async def add_user(user_id, step, time_s=None, language=None):
    """Create or update user row in DB. Only persistent status values are stored."""
    db_status = step if step in PERSISTENT_USER_STATUS_STEPS else None
    if db_status in LEGACY_STATUS_VALUES:
        db_status = None
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            if db_status is not None:
                existing_user.status = db_status
            if language is not None:
                existing_user.language = language
        else:
            session.add(
                User(
                    id=user_id,
                    status=db_status,
                    time_s=time_s,
                    amount=0,
                    language=language or "fa",
                )
            )
        await session.commit()
    if db_status is not None:
        _invalidate_status_local(user_id)


async def update_Money(user_id, Money, *, allow_negative: bool = True):
    async with Session() as session:
        stmt = select(User).filter_by(id=user_id)
        dialect = session.bind.dialect if session.bind is not None else None
        if dialect and dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            new_balance = int(existing_user.amount or 0) + int(Money)
            if not allow_negative and new_balance < 0:
                await session.rollback()
                return None
            existing_user.amount = new_balance
            await session.commit()
            return existing_user.amount
        return None


async def debit_Money_if_sufficient(user_id, amount):
    amount = int(amount)
    if amount < 0:
        raise ValueError("amount must be positive")
    return await update_Money(user_id, -amount, allow_negative=False)


async def get_Money(user_id):
    async with Session() as session:
        result = await session.execute(select(User).filter_by(id=user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user and existing_user.amount is not None:
            return existing_user.amount
        return 0


def user_safe_mode_value(user) -> bool | None:
    if not user:
        return None
    return getattr(user, "safe_mode", None)


def safe_mode_admin_label(value: bool | None) -> str:
    if value is True:
        return "✅ فعال"
    return "❌ غیرفعال"


async def all_users():
    async with Session() as session:
        result = await session.execute(select(func.count()).select_from(User))
        return result.scalar() or 0

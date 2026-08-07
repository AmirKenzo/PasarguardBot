from sqlalchemy import and_, distinct, func, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.broadcast import BroadcastJob
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.services import Service
from app.db.models.user import User
from app.logger import get_logger

logger = get_logger(__name__)


class BroadcastJobCRUD:
    """CRUD operations for BroadcastJob model."""

    async def create_job(
        self,
        created_by: int,
        target_mode: str,
        payload_json: dict,
        delay_ms: int = 300,
        batch_size: int = 50,
        batch_delay_ms: int = 2000,
    ) -> BroadcastJob:
        """Create a new broadcast job in draft status."""
        async with Session() as session:
            try:
                job = BroadcastJob(
                    created_by=created_by,
                    status="draft",
                    target_mode=target_mode,
                    payload_json=payload_json,
                    delay_ms=delay_ms,
                    batch_size=batch_size,
                    batch_delay_ms=batch_delay_ms,
                    cursor_user_id=0,
                )
                session.add(job)
                await session.commit()
                return job
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error creating broadcast job: {e}")
                raise

    async def get_job(self, job_id: int) -> BroadcastJob | None:
        """Get a broadcast job by ID."""
        async with Session() as session:
            try:
                result = await session.execute(select(BroadcastJob).filter_by(id=job_id))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                logger.error(f"Error getting broadcast job {job_id}: {e}")
                return None

    async def update_job(self, job_id: int, **kwargs) -> BroadcastJob | None:
        """Update a broadcast job."""
        async with Session() as session:
            try:
                result = await session.execute(select(BroadcastJob).filter_by(id=job_id))
                job = result.scalar_one_or_none()
                if job:
                    for key, value in kwargs.items():
                        if hasattr(job, key):
                            setattr(job, key, value)
                    await session.commit()
                    return job
                return None
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error updating broadcast job {job_id}: {e}")
                return None

    async def get_active_job(self) -> BroadcastJob | None:
        """Get the currently running broadcast job (if any)."""
        async with Session() as session:
            try:
                result = await session.execute(select(BroadcastJob).filter_by(status="running"))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                logger.error(f"Error getting active broadcast job: {e}")
                return None

    async def get_paused_job(self) -> BroadcastJob | None:
        """Get a paused broadcast job that can be resumed."""
        async with Session() as session:
            try:
                result = await session.execute(
                    select(BroadcastJob).filter_by(status="paused").order_by(BroadcastJob.id.desc())
                )
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                logger.error(f"Error getting paused broadcast job: {e}")
                return None

    async def get_queued_jobs(self) -> list[BroadcastJob]:
        """Get broadcast jobs confirmed by admin and waiting in queue."""
        async with Session() as session:
            try:
                result = await session.execute(
                    select(BroadcastJob).filter_by(status="queued").order_by(BroadcastJob.id.asc())
                )
                return list(result.scalars().all())
            except SQLAlchemyError as e:
                logger.error(f"Error getting queued broadcast jobs: {e}")
                return []

    async def get_queue_position(self, job_id: int) -> int:
        """Return 1-based queue position for a queued job, or 0 if not in queue."""
        queued_jobs = await self.get_queued_jobs()
        for index, job in enumerate(queued_jobs, start=1):
            if job.id == job_id:
                return index
        return 0

    async def get_next_queued_job(self) -> BroadcastJob | None:
        """Get the next queued broadcast job to auto-start."""
        queued_jobs = await self.get_queued_jobs()
        return queued_jobs[0] if queued_jobs else None

    async def count_queued_jobs(self) -> int:
        """Count number of confirmed broadcast jobs waiting in queue."""
        async with Session() as session:
            try:
                result = await session.execute(
                    select(func.count()).select_from(BroadcastJob).filter_by(status="queued")
                )
                return result.scalar() or 0
            except SQLAlchemyError as e:
                logger.error(f"Error counting queued broadcast jobs: {e}")
                return 0

    async def get_pending_jobs(self) -> list[BroadcastJob]:
        """Backward-compatible alias for queued jobs."""
        return await self.get_queued_jobs()

    async def get_next_pending_job(self) -> BroadcastJob | None:
        """Backward-compatible alias for next queued job."""
        return await self.get_next_queued_job()

    async def count_pending_jobs(self) -> int:
        """Backward-compatible alias for queued job count."""
        return await self.count_queued_jobs()

    async def get_incomplete_jobs(self) -> list[BroadcastJob]:
        """Get all incomplete broadcast jobs (not done or cancelled)."""
        async with Session() as session:
            try:
                result = await session.execute(
                    select(BroadcastJob)
                    .where(BroadcastJob.status.notin_(["done", "canceled"]))
                    .order_by(BroadcastJob.id.desc())
                )
                return list(result.scalars().all())
            except SQLAlchemyError as e:
                logger.error(f"Error getting incomplete broadcast jobs: {e}")
                return []

    async def delete_job(self, job_id: int) -> bool:
        """Delete a broadcast job."""
        async with Session() as session:
            try:
                result = await session.execute(select(BroadcastJob).filter_by(id=job_id))
                job = result.scalar_one_or_none()
                if job:
                    await session.delete(job)
                    await session.commit()
                    return True
                return False
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error deleting broadcast job {job_id}: {e}")
                return False

    async def count_targets(self, job_id: int) -> int:
        """Count the number of target users for a broadcast job."""
        async with Session() as session:
            try:
                job = await self.get_job(job_id)
                if not job:
                    return 0

                # Base query: exclude ban, BlockedBot and DeleteAccount (handle NULL safely)
                base_filter = or_(
                    User.status.is_(None),
                    and_(
                        User.status != "ban",
                        User.status != "BlockedBot",
                        User.status != "DeleteAccount",
                    ),
                )

                if job.target_mode == "all":
                    # All valid users
                    query = select(func.count()).select_from(User).where(base_filter)
                elif job.target_mode == "active":
                    # Active users (same as all valid users in this system)
                    query = select(func.count()).select_from(User).where(base_filter)
                elif job.target_mode == "users_with_active_service":
                    # Users with active service: enable=True and expiration_time > NOW()
                    import time

                    now = int(time.time())
                    # Count distinct user IDs with active services that match base filter
                    subquery = (
                        select(distinct(Service.id).label("user_id")).where(
                            and_(
                                Service.enable.is_(True),
                                Service.expiration_time.isnot(None),
                                Service.expiration_time > now,
                            )
                        )
                    ).subquery()

                    query = (
                        select(func.count(distinct(User.id)))
                        .select_from(User)
                        .join(subquery, User.id == subquery.c.user_id)
                        .where(base_filter)
                    )
                elif job.target_mode == "reseller_users":
                    subquery = select(distinct(ResellerAccount.telegram_id).label("user_id")).subquery()
                    query = (
                        select(func.count(distinct(User.id)))
                        .select_from(User)
                        .join(subquery, User.id == subquery.c.user_id)
                        .where(base_filter)
                    )
                elif job.target_mode == "blocked_users":
                    # Users who blocked the bot (step = BlockedBot)
                    query = select(func.count()).select_from(User).where(User.status == "BlockedBot")
                elif job.target_mode == "banned_users":
                    # Users banned by admin (step = ban)
                    query = select(func.count()).select_from(User).where(User.status == "ban")
                else:
                    return 0

                result = await session.execute(query)
                count = result.scalar() or 0

                # Update job with target count
                await self.update_job(job_id, total_targets=count)
                return count
            except SQLAlchemyError as e:
                logger.error(f"Error counting targets for job {job_id}: {e}")
                return 0

    async def get_target_users_batch(
        self,
        job_id: int,
        cursor_user_id: int = 0,
        batch_size: int = 50,
    ) -> list[User]:
        """Get a batch of target users starting from cursor_user_id."""
        async with Session() as session:
            try:
                job = await self.get_job(job_id)
                if not job:
                    return []

                # Base filter: exclude ban, BlockedBot and DeleteAccount, and id > cursor (handle NULL safely)
                base_filter = and_(
                    or_(
                        User.status.is_(None),
                        and_(
                            User.status != "ban",
                            User.status != "BlockedBot",
                            User.status != "DeleteAccount",
                        ),
                    ),
                    User.id > cursor_user_id,
                )

                if job.target_mode == "all":
                    query = select(User).where(base_filter).order_by(User.id).limit(batch_size)
                elif job.target_mode == "active":
                    # Same as all for this system
                    query = select(User).where(base_filter).order_by(User.id).limit(batch_size)
                elif job.target_mode == "users_with_active_service":
                    # Users with active service
                    import time

                    now = int(time.time())
                    # First get distinct user IDs with active services
                    subquery = (
                        select(distinct(Service.id).label("user_id")).where(
                            and_(
                                Service.enable.is_(True),
                                Service.expiration_time.isnot(None),
                                Service.expiration_time > now,
                            )
                        )
                    ).subquery()

                    # Then join with User table and apply base filter
                    query = (
                        select(User)
                        .join(subquery, User.id == subquery.c.user_id)
                        .where(base_filter)
                        .order_by(User.id)
                        .limit(batch_size)
                    )
                elif job.target_mode == "reseller_users":
                    subquery = select(distinct(ResellerAccount.telegram_id).label("user_id")).subquery()
                    query = (
                        select(User)
                        .join(subquery, User.id == subquery.c.user_id)
                        .where(base_filter)
                        .order_by(User.id)
                        .limit(batch_size)
                    )
                elif job.target_mode == "blocked_users":
                    # Users who blocked the bot (step = BlockedBot)
                    query = (
                        select(User)
                        .where(and_(User.status == "BlockedBot", User.id > cursor_user_id))
                        .order_by(User.id)
                        .limit(batch_size)
                    )
                elif job.target_mode == "banned_users":
                    # Users banned by admin (step = ban)
                    query = (
                        select(User)
                        .where(and_(User.status == "ban", User.id > cursor_user_id))
                        .order_by(User.id)
                        .limit(batch_size)
                    )
                else:
                    return []

                result = await session.execute(query)
                users = result.scalars().all()
                return list(users)
            except SQLAlchemyError as e:
                logger.error(f"Error getting target users batch for job {job_id}: {e}")
                return []

    async def increment_counters(
        self,
        job_id: int,
        sent_ok: int = 0,
        sent_fail: int = 0,
        blocked: int = 0,
        deleted: int = 0,
        floodwait_count: int = 0,
    ) -> bool:
        """Increment job counters atomically."""
        async with Session() as session:
            try:
                values = {}
                if sent_ok:
                    values["sent_ok"] = BroadcastJob.sent_ok + sent_ok
                if sent_fail:
                    values["sent_fail"] = BroadcastJob.sent_fail + sent_fail
                if blocked:
                    values["blocked"] = BroadcastJob.blocked + blocked
                if deleted:
                    values["deleted"] = BroadcastJob.deleted + deleted
                if floodwait_count:
                    values["floodwait_count"] = BroadcastJob.floodwait_count + floodwait_count
                if not values:
                    return True
                result = await session.execute(update(BroadcastJob).where(BroadcastJob.id == job_id).values(**values))
                if result.rowcount:
                    await session.commit()
                    return True
                return False
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error incrementing counters for job {job_id}: {e}")
                return False

    async def update_cursor(self, job_id: int, cursor_user_id: int) -> bool:
        """Update the cursor position for a job."""
        async with Session() as session:
            try:
                result = await session.execute(select(BroadcastJob).filter_by(id=job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.cursor_user_id = cursor_user_id
                    await session.commit()
                    return True
                return False
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Error updating cursor for job {job_id}: {e}")
                return False

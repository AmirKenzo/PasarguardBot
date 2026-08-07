"""
Broadcast Manager - Production-grade job-based broadcast system for Telethon.

Features:
- Persistent job system with SQLAlchemy
- MySQL named locks for single active broadcast enforcement
- Pause/Resume/Cancel support
- FloodWait handling
- Progress tracking
- Error mapping to user.status
"""

import asyncio
import time

from telethon import errors

from app.db.base import DATABASE_DIALECT, AsyncSessionLocal as Session
from app.db.crud.broadcast import BroadcastJobCRUD
from app.db.redis import get_redis
from app.logger import get_logger
from app.services.broadcast.markup import sanitize_payload_json
from app.services.broadcast.sender import BroadcastSender
from app.telegram.state.keys import build_cache_key

logger = get_logger(__name__)

# Global task reference for the active worker
_active_worker_task: asyncio.Task | None = None
EMPTY_TARGET_RECHECK_SECONDS = 3
EMPTY_TARGET_RECHECK_ATTEMPTS = 1
COUNT_TARGETS_EVERY_N_BATCHES = 10
_BROADCAST_LOCK_REDIS_KEY = build_cache_key("broadcast:manager:lock")
_BROADCAST_LOCK_TTL_SECONDS = 7200

# In-process pause/cancel signals so the worker avoids a DB round-trip per recipient.
_job_runtime_status: dict[int, str] = {}


def set_job_runtime_status(job_id: int, status: str) -> None:
    _job_runtime_status[job_id] = status


def get_job_runtime_status(job_id: int) -> str | None:
    return _job_runtime_status.get(job_id)


def clear_job_runtime_status(job_id: int) -> None:
    _job_runtime_status.pop(job_id, None)


class BroadcastManager:
    """Manages broadcast jobs with persistent storage and worker tasks."""

    def __init__(self):
        self.job_crud = BroadcastJobCRUD()
        self.sender = BroadcastSender()
        self._worker_task: asyncio.Task | None = None
        self._mysql_lock_session = None
        self._redis_lock_held = False
        self._count_targets_batch_counter = 0

    async def acquire_lock(self, lock_wait_seconds: int = 0, *, job_id: int | None = None) -> bool:
        """
        Acquire a single-active-broadcast lock.
        Prefer Redis (does not pin a MySQL pool connection); fall back to GET_LOCK.
        """
        if DATABASE_DIALECT != "mysql":
            # For non-MySQL databases, use a simple check (not as safe across processes)
            active_job = await self.job_crud.get_active_job()
            logger.debug(f"Non-MySQL lock check: active_job={active_job.id if active_job else None}")
            return active_job is None or (job_id is not None and active_job.id == job_id)

        if self._redis_lock_held or self._mysql_lock_session is not None:
            return True

        redis = await get_redis()
        if redis is not None:
            try:
                ok = await redis.set(
                    _BROADCAST_LOCK_REDIS_KEY,
                    str(job_id or 1),
                    nx=True,
                    ex=_BROADCAST_LOCK_TTL_SECONDS,
                )
                if ok:
                    self._redis_lock_held = True
                    return True
                # Another process holds the lock.
                return False
            except Exception as e:
                logger.warning("Redis broadcast lock failed, falling back to MySQL: %s", e)

        session = Session()
        try:
            from sqlalchemy import text

            result = await session.execute(text(f"SELECT GET_LOCK('broadcast_manager_lock', {lock_wait_seconds})"))
            lock_result = result.scalar()
            logger.debug(f"MySQL lock acquire result: {lock_result} (1=acquired, 0=timeout, NULL=error)")
            if lock_result == 1:
                self._mysql_lock_session = session
                return True
            await session.close()
            return False
        except Exception as e:
            await session.close()
            self._mysql_lock_session = None
            logger.error(f"Error acquiring MySQL lock: {e}", exc_info=True)
            return False

    async def release_lock(self) -> bool:
        """Release broadcast lock (Redis or MySQL)."""
        if DATABASE_DIALECT != "mysql":
            logger.debug("Non-MySQL database: no lock to release")
            return True

        if self._redis_lock_held:
            self._redis_lock_held = False
            redis = await get_redis()
            if redis is not None:
                try:
                    await redis.delete(_BROADCAST_LOCK_REDIS_KEY)
                except Exception as e:
                    logger.warning("Redis broadcast lock release failed: %s", e)
            return True

        if self._mysql_lock_session is None:
            logger.debug("MySQL lock not held by this manager instance")
            return True

        session = self._mysql_lock_session
        self._mysql_lock_session = None
        try:
            from sqlalchemy import text

            result = await session.execute(text("SELECT RELEASE_LOCK('broadcast_manager_lock')"))
            released = result.scalar()
            logger.debug(f"MySQL lock release result: {released} (1=released, 0=not held, NULL=error)")
            return released == 1
        except Exception as e:
            logger.error(f"Error releasing MySQL lock: {e}", exc_info=True)
            return False
        finally:
            await session.close()

    async def create_job(
        self,
        created_by: int,
        target_mode: str,
        payload_json: dict,
        delay_ms: int = 0,
        batch_size: int = 10,
        batch_delay_ms: int = 2000,
    ) -> int | None:
        """
        Create a new broadcast job in draft status.
        Returns job_id or None on error.
        """
        try:
            job = await self.job_crud.create_job(
                created_by=created_by,
                target_mode=target_mode,
                payload_json=sanitize_payload_json(payload_json),
                delay_ms=delay_ms,
                batch_size=batch_size,
                batch_delay_ms=batch_delay_ms,
            )
            logger.info(f"Created broadcast job {job.id} by user {created_by}")
            return job.id
        except Exception as e:
            logger.error(f"Error creating broadcast job: {e}")
            return None

    async def count_targets(self, job_id: int) -> int:
        """Count target users for a job."""
        return await self.job_crud.count_targets(job_id)

    async def send_test(self, job_id: int, admin_id: int) -> tuple[bool, str]:
        """Send a test message to the admin who created the job."""
        try:
            job = await self.job_crud.get_job(job_id)
            if not job:
                return False, "❌ کار پیدا نشد!"

            return await self.sender.send_test(job, admin_id)
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
            return False, "❌ خطا در ارسال پیام تست!"

    async def cleanup_stuck_jobs(self):
        """Clean up jobs that are stuck in 'running' status but have no active worker."""
        try:
            active_job = await self.job_crud.get_active_job()
            if active_job and active_job.started_at:
                # Check if job has been running for more than 1 hour without progress
                # This indicates a stuck job
                elapsed = int(time.time()) - active_job.started_at
                if elapsed > 3600:  # 1 hour
                    logger.warning(f"Found stuck job {active_job.id} running for {elapsed}s, marking as failed")
                    # Force release lock before marking as failed
                    await self.release_lock()
                    await self.job_crud.update_job(
                        active_job.id,
                        status="failed",
                        error_message=f"Job stuck for {elapsed} seconds",
                        finished_at=int(time.time()),
                    )
                    return True
            return False
        except Exception as e:
            logger.error(f"Error cleaning up stuck jobs: {e}")
            return False

    async def _cleanup_previous_worker(self) -> bool:
        """Cancel previous worker task and release lock if needed. Returns True if cleanup ran."""
        cleaned = False
        try:
            if self._worker_task and not self._worker_task.done():
                cleaned = True
                logger.warning("Canceling previous worker task")
                self._worker_task.cancel()
                try:
                    await asyncio.wait_for(self._worker_task, timeout=1.0)
                except TimeoutError, asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error waiting for canceled worker task: {e}")
                self._worker_task = None

            if self._redis_lock_held or self._mysql_lock_session is not None:
                cleaned = True
                await self.release_lock()

            if cleaned:
                await asyncio.sleep(0.1)
                logger.debug("Previous worker cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up previous worker: {e}")
        return cleaned

    async def _begin_running_job(self, job_id: int, *, skip_cleanup: bool = False) -> tuple[bool, str]:
        """Acquire lock, mark job running, and spawn worker."""
        job = await self.job_crud.get_job(job_id)
        if not job:
            return False, "Job not found"

        if job.status not in ("pending_confirm", "queued"):
            return False, f"Job status is {job.status}, expected pending_confirm or queued"

        if not skip_cleanup:
            needs_cleanup = (
                (self._worker_task is not None and not self._worker_task.done())
                or self._redis_lock_held
                or self._mysql_lock_session is not None
            )
            if needs_cleanup:
                await self._cleanup_previous_worker()
            else:
                await self.cleanup_stuck_jobs()

        active_job = await self.job_crud.get_active_job()
        if active_job and active_job.id != job_id:
            logger.warning(
                f"Cannot start job {job_id}: another job {active_job.id} is running (status={active_job.status})"
            )
            if not skip_cleanup:
                await self._cleanup_previous_worker()
            await self.job_crud.update_job(
                active_job.id,
                status="failed",
                error_message="Replaced by new broadcast",
                finished_at=int(time.time()),
            )

        logger.info(f"Attempting to acquire lock for job {job_id} before starting")
        lock_acquired_here = False
        try:
            if not await self.acquire_lock(lock_wait_seconds=0, job_id=job_id):
                logger.error(f"Could not acquire lock for job {job_id}. Lock may be held by another process.")
                return False, "Could not acquire lock. Another broadcast may be running."

            lock_acquired_here = True

            job = await self.job_crud.update_job(
                job_id,
                status="running",
                started_at=int(time.time()),
            )

            if not job:
                await self.release_lock()
                return False, "Failed to update job status"

            set_job_runtime_status(job_id, "running")
            self._worker_task = asyncio.create_task(self._worker_loop(job_id, lock_already_acquired=True))

            logger.info(f"Broadcast job {job_id} started (lock acquired)")
            return True, "Broadcast started successfully"
        except Exception as e:
            logger.error(f"Error starting broadcast job {job_id}: {e}")
            if lock_acquired_here:
                await self.release_lock()
            return False, f"Error starting broadcast: {e}"

    async def confirm_start(self, job_id: int) -> tuple[bool, str]:
        """
        Confirm and start a broadcast job.
        Returns (success, message).
        """
        try:
            return await self._begin_running_job(job_id, skip_cleanup=False)
        except Exception as e:
            logger.error(f"Error in confirm_start: {e}")
            return False, str(e)

    async def pause_job(self, job_id: int) -> tuple[bool, str]:
        """Pause a running broadcast job."""
        try:
            job = await self.job_crud.get_job(job_id)
            if not job:
                return False, "Job not found"

            if job.status != "running":
                return False, f"Job status is {job.status}, cannot pause"

            # Update status - worker will check and pause
            job = await self.job_crud.update_job(job_id, status="paused")
            if job:
                set_job_runtime_status(job_id, "paused")
                logger.info(f"Broadcast job {job_id} paused")
                return True, "Job paused successfully"
            return False, "Failed to pause job"
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")
            return False, str(e)

    async def resume_job(self, job_id: int) -> tuple[bool, str]:
        """Resume a paused broadcast job."""
        try:
            job = await self.job_crud.get_job(job_id)
            if not job:
                return False, "Job not found"

            if job.status != "paused":
                return False, f"Job status is {job.status}, cannot resume"

            # Clean up any stuck jobs and previous worker first
            await self.cleanup_stuck_jobs()
            await self._cleanup_previous_worker()

            # Wait a bit to ensure cleanup is complete
            await asyncio.sleep(0.5)

            # Check if another job is running
            active_job = await self.job_crud.get_active_job()
            if active_job and active_job.id != job_id:
                logger.warning(f"Cannot resume job {job_id}: another job {active_job.id} is running")
                # Force cleanup the stuck job
                await self._cleanup_previous_worker()
                await asyncio.sleep(0.5)
                # Try to mark the old job as failed
                await self.job_crud.update_job(
                    active_job.id,
                    status="failed",
                    error_message="Replaced by resumed broadcast",
                    finished_at=int(time.time()),
                )

            # CRITICAL: Acquire lock BEFORE changing status to "running"
            logger.info(f"Attempting to acquire lock for job {job_id} before resuming")
            lock_acquired_here = False
            try:
                if not await self.acquire_lock(lock_wait_seconds=3, job_id=job_id):
                    logger.error(f"Could not acquire lock for job {job_id}. Lock may be held by another process.")
                    return False, "Could not acquire lock. Another broadcast may be running."

                lock_acquired_here = True

                # Update status to running (lock is already acquired)
                job = await self.job_crud.update_job(job_id, status="running")
                if not job:
                    # Release lock if job update failed
                    await self.release_lock()
                    return False, "Failed to update job status"

                set_job_runtime_status(job_id, "running")
                # Spawn worker task (lock is already acquired, worker will use it)
                self._worker_task = asyncio.create_task(self._worker_loop(job_id, lock_already_acquired=True))

                logger.info(f"Broadcast job {job_id} resumed (lock acquired)")
                return True, "Job resumed successfully"
            except Exception as e:
                logger.error(f"Error resuming job {job_id}: {e}")
                # Release lock if we acquired it but something went wrong
                if lock_acquired_here:
                    await self.release_lock()
                return False, str(e)
        except Exception as e:
            logger.error(f"Error in resume_job: {e}")
            return False, str(e)

    async def cancel_job(self, job_id: int) -> tuple[bool, str]:
        """Cancel a broadcast job."""
        try:
            job = await self.job_crud.get_job(job_id)
            if not job:
                return False, "Job not found"

            if job.status in ["done", "canceled", "failed"]:
                return False, f"Job status is {job.status}, cannot cancel"

            # Cancel worker task if it's for this job
            if self._worker_task and not self._worker_task.done():
                logger.info(f"Canceling worker task for job {job_id}")
                self._worker_task.cancel()
                try:
                    await asyncio.wait_for(self._worker_task, timeout=2.0)
                except TimeoutError, asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error waiting for canceled worker: {e}")
                self._worker_task = None

            set_job_runtime_status(job_id, "canceled")
            # Update status - worker will check and stop
            job = await self.job_crud.update_job(
                job_id,
                status="canceled",
                finished_at=int(time.time()),
            )

            # Release lock if this was the active job
            if job and job.status == "canceled":
                await self.release_lock()

            if job:
                logger.info(f"Broadcast job {job_id} canceled")
                # Delete canceled job from database
                await self.job_crud.delete_job(job_id)
                clear_job_runtime_status(job_id)
                self.sender.clear_job_cache(job_id)
                logger.info(f"Canceled job {job_id} deleted from database")
                return True, "Job canceled successfully"
            return False, "Failed to cancel job"
        except Exception as e:
            logger.error(f"Error canceling job {job_id}: {e}")
            return False, str(e)

    async def get_status(self, job_id: int) -> dict | None:
        """Get current status of a broadcast job."""
        try:
            job = await self.job_crud.get_job(job_id)
            if not job:
                return None

            total = job.total_targets
            completed = job.sent_ok + job.sent_fail + job.blocked + job.deleted
            progress_percent = (completed / total * 100) if total > 0 else 0.0

            # Get total floodwait seconds from payload_json
            total_floodwait_seconds = job.payload_json.get("_total_floodwait_seconds", 0)

            return {
                "id": job.id,
                "status": job.status,
                "target_mode": job.target_mode,
                "total_targets": total,
                "sent_ok": job.sent_ok,
                "sent_fail": job.sent_fail,
                "blocked": job.blocked,
                "deleted": job.deleted,
                "floodwait_count": job.floodwait_count,
                "total_floodwait_seconds": total_floodwait_seconds,
                "progress_percent": progress_percent,
                "cursor_user_id": job.cursor_user_id,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
            }
        except Exception as e:
            logger.error(f"Error getting job status {job_id}: {e}")
            return None

    async def _worker_loop(self, job_id: int, lock_already_acquired: bool = False):
        """
        Main worker loop for processing broadcast jobs.
        Handles batching, delays, floodwait, pause/cancel checks, and error mapping.

        Args:
            job_id: The job ID to process
            lock_already_acquired: If True, lock was already acquired in confirm_start()
        """
        lock_acquired = lock_already_acquired
        handed_off_to_next_job = False
        try:
            if not lock_already_acquired:
                # Check for active jobs first (only if lock not already acquired)
                active_job = await self.job_crud.get_active_job()
                if active_job and active_job.id != job_id:
                    logger.warning(f"Worker for job {job_id} found another active job {active_job.id}, cannot start")
                    await self.job_crud.update_job(
                        job_id,
                        status="failed",
                        error_message=f"Another job {active_job.id} is running",
                        finished_at=int(time.time()),
                    )
                    return

                # Ensure lock is held
                # Use timeout of 3 seconds to allow previous worker to release lock
                logger.info(
                    f"Worker for job {job_id} attempting to acquire lock (database={DATABASE_DIALECT}, timeout=3s)"
                )
                if not await self.acquire_lock(lock_wait_seconds=3, job_id=job_id):
                    logger.error(
                        f"Worker for job {job_id} could not acquire lock after 3 seconds. Checking for active jobs..."
                    )
                    # Double-check: maybe another job is running
                    active_job = await self.job_crud.get_active_job()
                    if active_job and active_job.id != job_id:
                        logger.error(f"Active job found: {active_job.id} (status={active_job.status})")
                        await self.job_crud.update_job(
                            job_id,
                            status="failed",
                            error_message=f"Another job {active_job.id} is running",
                            finished_at=int(time.time()),
                        )
                        return
                    logger.error("No active job found, but lock acquisition failed. This may indicate a stuck lock.")
                    # Try force release and retry
                    await self.release_lock()
                    await asyncio.sleep(0.5)
                    if not await self.acquire_lock(lock_wait_seconds=2, job_id=job_id):
                        logger.error("Still cannot acquire lock after force release. Marking job as failed.")
                        await self.job_crud.update_job(
                            job_id,
                            status="failed",
                            error_message="Could not acquire lock (stuck lock)",
                            finished_at=int(time.time()),
                        )
                        return
                    logger.info("Lock acquired after force release")

                lock_acquired = True

            logger.info(f"Worker started for job {job_id} (lock acquired={lock_acquired})")

            # Initial check: verify job exists and get initial state
            job = await self.job_crud.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found at worker start")
                await self.release_lock()
                return

            logger.info(
                f"Job {job_id} initial state: status={job.status}, total_targets={job.total_targets}, cursor={job.cursor_user_id}"
            )
            set_job_runtime_status(job_id, job.status)
            empty_target_attempts = 0

            while True:
                runtime_status = get_job_runtime_status(job_id)
                if runtime_status == "canceled":
                    logger.info(f"Job {job_id} was canceled, stopping worker")
                    break

                if runtime_status == "paused":
                    logger.info(f"Job {job_id} is paused, waiting...")
                    await asyncio.sleep(2)
                    continue

                # Refresh job fields once per batch (not per recipient).
                job = await self.job_crud.get_job(job_id)
                if not job:
                    logger.error(f"Job {job_id} not found in worker")
                    break

                if job.status == "canceled":
                    set_job_runtime_status(job_id, "canceled")
                    logger.info(f"Job {job_id} was canceled, stopping worker")
                    break

                if job.status == "paused":
                    set_job_runtime_status(job_id, "paused")
                    logger.info(f"Job {job_id} is paused, waiting...")
                    await asyncio.sleep(2)
                    continue

                if job.status != "running":
                    logger.warning(f"Job {job_id} status is {job.status}, stopping worker")
                    break

                set_job_runtime_status(job_id, "running")

                # Refresh target count on a cadence (not every batch) so users added
                # mid-broadcast are still reflected without constant COUNT scans.
                self._count_targets_batch_counter += 1
                should_recount = (
                    not job.total_targets
                    or self._count_targets_batch_counter == 1
                    or self._count_targets_batch_counter % COUNT_TARGETS_EVERY_N_BATCHES == 0
                )
                if should_recount and ((job.cursor_user_id or 0) > 0 or not job.total_targets):
                    await self.count_targets(job_id)

                # Get batch of users
                logger.info(
                    f"Job {job_id}: Fetching users batch (cursor={job.cursor_user_id or 0}, batch_size={job.batch_size})"
                )
                users = await self.job_crud.get_target_users_batch(
                    job_id,
                    cursor_user_id=job.cursor_user_id or 0,
                    batch_size=job.batch_size,
                )

                logger.info(f"Job {job_id}: Found {len(users) if users else 0} users in batch")

                if not users:
                    job = await self.job_crud.get_job(job_id)
                    completed = 0
                    total = 0
                    if job:
                        completed = job.sent_ok + job.sent_fail + job.blocked + job.deleted
                        total = job.total_targets or 0

                    if total > 0 and completed >= total:
                        logger.info(f"Job {job_id}: All {total} targets processed ({completed}), finishing immediately")
                    else:
                        empty_target_attempts += 1
                        if empty_target_attempts <= EMPTY_TARGET_RECHECK_ATTEMPTS:
                            logger.info(
                                f"Job {job_id}: No targets after cursor {job.cursor_user_id or 0}; "
                                f"waiting {EMPTY_TARGET_RECHECK_SECONDS}s for newly registered users "
                                f"({empty_target_attempts}/{EMPTY_TARGET_RECHECK_ATTEMPTS})"
                            )
                            await asyncio.sleep(EMPTY_TARGET_RECHECK_SECONDS)
                            continue

                    # No more users, job is done
                    logger.info(f"Job {job_id}: No more users, marking as done")
                    if lock_acquired:
                        await self.release_lock()
                        lock_acquired = False
                    await self.job_crud.update_job(
                        job_id,
                        status="done",
                        finished_at=int(time.time()),
                    )
                    clear_job_runtime_status(job_id)
                    self.sender.clear_job_cache(job_id)
                    logger.info(
                        f"Job {job_id} completed successfully (status=done, monitor will show final message and delete)"
                    )

                    handed_off_to_next_job = await self._start_next_queued_broadcast()
                    break

                empty_target_attempts = 0

                # Process batch
                batch_sent_ok = 0
                batch_sent_fail = 0
                batch_blocked = 0
                batch_deleted = 0
                batch_floodwait = 0
                last_user_id = job.cursor_user_id or 0

                logger.info(f"Job {job_id}: Processing {len(users)} users in batch")

                for idx, user in enumerate(users, 1):
                    # Re-check pause/cancel without a DB round-trip per recipient.
                    runtime_status = get_job_runtime_status(job_id)
                    if runtime_status in ("canceled", "paused"):
                        logger.info(f"Job {job_id}: Status changed to {runtime_status}, stopping batch")
                        break

                    last_user_id = user.id
                    logger.debug("Job %s: Sending to user ID: %s (%s/%s)", job_id, user.id, idx, len(users))

                    try:
                        # Send message
                        success, status = await self.sender.send_to_user(job, user.id)

                        if success:
                            batch_sent_ok += 1
                            logger.debug("Job %s: Successfully sent to user ID: %s", job_id, user.id)
                        elif status == "blocked":
                            batch_blocked += 1
                            logger.warning(f"🚫 [Job {job_id}] User ID {user.id} blocked the bot")
                        elif status == "deleted":
                            batch_deleted += 1
                            logger.warning(f"🗑️ [Job {job_id}] User ID {user.id} account deleted/deactivated")
                        else:
                            batch_sent_fail += 1
                            logger.error(f"❌ [Job {job_id}] Failed to send to user ID: {user.id}, status: {status}")

                        # Apply delay
                        await asyncio.sleep(job.delay_ms / 1000.0)

                    except errors.FloodWaitError as e:
                        batch_floodwait += 1
                        floodwait_seconds = e.seconds
                        # Wait EXACTLY for the floodwait period (no jitter, be precise)
                        # CRITICAL: Don't send to next user, wait here for the SAME user
                        logger.warning(
                            f"⏳ [Job {job_id}] FloodWait for user ID {user.id}: waiting EXACTLY {floodwait_seconds}s - PAUSING all sends"
                        )

                        # Update total floodwait seconds in payload_json for status display
                        job = await self.job_crud.get_job(job_id)
                        if job:
                            payload = job.payload_json.copy()
                            current_total = payload.get("_total_floodwait_seconds", 0)
                            payload["_total_floodwait_seconds"] = current_total + floodwait_seconds
                            await self.job_crud.update_job(job_id, payload_json=payload)

                        # Wait EXACTLY here - don't skip to next user
                        await asyncio.sleep(floodwait_seconds)

                        logger.debug(
                            "Job %s: FloodWait finished for user ID %s, retrying send...",
                            job_id,
                            user.id,
                        )

                        # Retry to the SAME user after floodwait
                        try:
                            success, status = await self.sender.send_to_user(job, user.id)
                            if success:
                                batch_sent_ok += 1
                                logger.debug(
                                    "Job %s: Successfully sent to user ID: %s (after %ss FloodWait)",
                                    job_id,
                                    user.id,
                                    floodwait_seconds,
                                )
                            elif status == "blocked":
                                batch_blocked += 1
                                logger.warning(f"🚫 [Job {job_id}] User ID {user.id} blocked the bot (after FloodWait)")
                            elif status == "deleted":
                                batch_deleted += 1
                                logger.warning(
                                    f"🗑️ [Job {job_id}] User ID {user.id} account deleted/deactivated (after FloodWait)"
                                )
                            elif status == "floodwait":
                                # Another floodwait - wait again for the SAME user
                                batch_floodwait += 1
                                retry_e = errors.FloodWaitError(request=None, seconds=0)
                                # Get the actual seconds from the exception if possible
                                # For now, mark as failed to avoid infinite loop
                                batch_sent_fail += 1
                                logger.error(
                                    f"❌ [Job {job_id}] User ID {user.id} got FloodWait again after waiting, marking as failed"
                                )
                            else:
                                batch_sent_fail += 1
                                logger.error(
                                    f"❌ [Job {job_id}] Failed to send to user ID: {user.id} after FloodWait, status: {status}"
                                )
                        except errors.FloodWaitError as retry_e:
                            # Another floodwait - wait again for the SAME user (don't skip)
                            batch_floodwait += 1
                            retry_floodwait_seconds = retry_e.seconds
                            logger.warning(
                                f"⏳ [Job {job_id}] User ID {user.id} got FloodWait again: waiting EXACTLY {retry_floodwait_seconds}s"
                            )

                            # Update total floodwait seconds
                            job = await self.job_crud.get_job(job_id)
                            if job:
                                payload = job.payload_json.copy()
                                current_total = payload.get("_total_floodwait_seconds", 0)
                                payload["_total_floodwait_seconds"] = current_total + retry_floodwait_seconds
                                await self.job_crud.update_job(job_id, payload_json=payload)

                            await asyncio.sleep(retry_floodwait_seconds)

                            # Final retry
                            try:
                                success, status = await self.sender.send_to_user(job, user.id)
                                if success:
                                    batch_sent_ok += 1
                                    logger.debug(
                                        "Job %s: Successfully sent to user ID: %s (after 2nd FloodWait)",
                                        job_id,
                                        user.id,
                                    )
                                elif status == "blocked":
                                    batch_blocked += 1
                                elif status == "deleted":
                                    batch_deleted += 1
                                else:
                                    batch_sent_fail += 1
                                    logger.error(
                                        f"❌ [Job {job_id}] User ID {user.id} failed after 2nd FloodWait, marking as failed"
                                    )
                            except Exception as final_e:
                                batch_sent_fail += 1
                                logger.error(f"❌ [Job {job_id}] Final retry failed for user ID {user.id}: {final_e}")
                                await self.sender.handle_send_error(job, user.id, final_e)
                        except Exception as retry_e:
                            logger.error(f"❌ [Job {job_id}] Retry failed for user ID {user.id}: {retry_e}")
                            batch_sent_fail += 1
                            await self.sender.handle_send_error(job, user.id, retry_e)

                    except Exception as e:
                        batch_sent_fail += 1
                        logger.error(f"❌ [Job {job_id}] Error sending to user ID {user.id}: {type(e).__name__}: {e}")
                        await self.sender.handle_send_error(job, user.id, e)

                # Update counters and cursor in batch
                await self.job_crud.increment_counters(
                    job_id,
                    sent_ok=batch_sent_ok,
                    sent_fail=batch_sent_fail,
                    blocked=batch_blocked,
                    deleted=batch_deleted,
                    floodwait_count=batch_floodwait,
                )
                await self.job_crud.update_cursor(job_id, last_user_id)

                logger.info(
                    f"📊 [Job {job_id}] Batch summary: ✅ {batch_sent_ok} sent | "
                    f"❌ {batch_sent_fail} failed | 🚫 {batch_blocked} blocked | "
                    f"🗑️ {batch_deleted} deleted | ⏳ {batch_floodwait} FloodWait | "
                    f"📍 Cursor: {last_user_id}"
                )

                # Delay between batches only when a full batch was sent (more may remain)
                if job.batch_delay_ms > 0 and len(users) >= job.batch_size:
                    batch_delay_seconds = job.batch_delay_ms / 1000.0
                    logger.info(f"⏸️ [Job {job_id}] Waiting {batch_delay_seconds:.1f}s before next batch...")
                    await asyncio.sleep(batch_delay_seconds)

        except asyncio.CancelledError:
            logger.info(f"Worker for job {job_id} was cancelled")
            if lock_acquired:
                await self.release_lock()
                lock_acquired = False
            logger.info(f"Broadcast job {job_id} left resumable after worker cancellation")
            raise
        except Exception as e:
            logger.error(f"Worker error for job {job_id}: {e}", exc_info=True)
            # Release lock before marking as failed
            if lock_acquired:
                await self.release_lock()
            await self.job_crud.update_job(
                job_id,
                status="failed",
                error_message=str(e),
                finished_at=int(time.time()),
            )
            clear_job_runtime_status(job_id)
            self.sender.clear_job_cache(job_id)
        finally:
            if lock_acquired:
                logger.debug(f"Releasing lock for job {job_id}")
                released = await self.release_lock()
                if not released:
                    logger.warning(f"Failed to release lock for job {job_id}")
            else:
                logger.debug(f"No lock to release for job {job_id} (lock was never acquired)")
            if not handed_off_to_next_job:
                self._worker_task = None
            logger.info(f"Worker finished for job {job_id}")

    async def _start_next_queued_broadcast(self) -> bool:
        """Check for pending broadcasts and start the next one."""
        try:
            next_job = await self.job_crud.get_next_queued_job()
            if next_job:
                logger.info(f"📢 Starting queued broadcast {next_job.id}")
                success, message = await self._begin_running_job(next_job.id, skip_cleanup=True)
                if success:
                    logger.info(f"✅ Successfully started queued broadcast {next_job.id}")
                else:
                    logger.error(f"❌ Failed to start queued broadcast {next_job.id}: {message}")
                return success
            return False
        except Exception as e:
            logger.error(f"Error starting next queued broadcast: {e}", exc_info=True)
            return False

    async def resume_running_broadcasts(self):
        """Resume monitoring for any running broadcasts after bot restart."""
        try:
            active_job = await self.job_crud.get_active_job()
            if active_job:
                logger.info(f"🔄 Resuming broadcast {active_job.id} after restart")
                # Restart the worker task
                if not self._worker_task or self._worker_task.done():
                    self._worker_task = asyncio.create_task(self._worker_loop(active_job.id))
                    logger.info(f"✅ Worker task restarted for broadcast {active_job.id}")
        except Exception as e:
            logger.error(f"Error resuming running broadcasts: {e}", exc_info=True)


# Global manager instance
broadcast_manager = BroadcastManager()

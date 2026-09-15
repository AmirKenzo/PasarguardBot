"""APScheduler instance and lifecycle."""

from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.logger import LogTag, get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()

# APScheduler doesn't track a job's last run itself — only its upcoming
# next_run_time. This mirrors run completions (success or error, either way
# the job *ran*) into an in-memory map so the admin panel can show both
# "last ran" and "next run" for each job. Reset on process restart, same as
# next_run_time already implicitly is.
_last_run_times: dict[str, datetime] = {}


def _record_job_run(event: JobExecutionEvent) -> None:
    _last_run_times[event.job_id] = event.scheduled_run_time


def get_last_run(job_id: str) -> datetime | None:
    return _last_run_times.get(job_id)


def start_scheduler() -> None:
    """Register all jobs and start the scheduler (call after bot is ready)."""
    from app.jobs.registry import register_all_jobs

    if scheduler.running:
        logger.warning("%s Already running — skipped start", LogTag.SCHEDULER)
        return
    register_all_jobs()
    scheduler.add_listener(_record_job_run, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    jobs_count = len(scheduler.get_jobs())
    scheduler.start()
    logger.info("%s Started | jobs=%s", LogTag.SCHEDULER, jobs_count)

"""Central job registration — single source of truth for all scheduled jobs.

Legacy reseller modules ``hourly_billing.py`` / ``usage_billing.py`` are unused
and intentionally not registered here (avoids double-charge if re-enabled by mistake).
"""

from datetime import datetime, timedelta

from app.jobs.scheduler import scheduler
from app.logger import LogTag, get_logger

logger = get_logger(__name__)

_JOBS_REGISTERED = False
_JOB_STAGGER_SECONDS = 5
_JOB_JITTER_SECONDS = 10
_JOB_MISFIRE_GRACE_SECONDS = 30


def register_all_jobs() -> None:
    global _JOBS_REGISTERED
    if _JOBS_REGISTERED:
        return

    from app.jobs.backup import bootstrap_backup_job, register_backup_job_placeholder
    from app.jobs.panels.cleanup import get_cookies
    from app.jobs.payments.transactions import (
        auto_confirm_job,
        ton_checking,
        trx_checking,
        usdt_checking,
    )
    from app.jobs.prices import get_prices_and_update
    from app.jobs.reseller.billing import run_reseller_billing
    from app.jobs.reseller.low_balance_warning import run_reseller_low_balance_warning
    from app.jobs.services.expiration import handle_service_expiration
    from app.jobs.services.low_volume import check_low_volume

    now = datetime.now()
    job_defs = [
        (handle_service_expiration, "interval", {"seconds": 60}, "service_expiration_handler"),
        (check_low_volume, "interval", {"seconds": 60}, "check_low_volume"),
        (get_cookies, "interval", {"hours": 5}, "get_cookies"),
        (get_prices_and_update, "interval", {"minutes": 10}, "get_prices_and_update"),
        (auto_confirm_job, "interval", {"seconds": 60}, "auto_confirm_job"),
        (trx_checking, "interval", {"seconds": 60}, "trx_checking"),
        (usdt_checking, "interval", {"seconds": 60}, "usdt_checking"),
        (ton_checking, "interval", {"seconds": 60}, "ton_checking"),
        (run_reseller_billing, "interval", {"seconds": 60}, "reseller_billing"),
        (run_reseller_low_balance_warning, "interval", {"minutes": 5}, "reseller_low_balance_warning"),
    ]

    for i, (func, trigger, trigger_args, job_id) in enumerate(job_defs):
        scheduler.add_job(
            func,
            trigger,
            id=job_id,
            replace_existing=True,
            next_run_time=now + timedelta(seconds=_JOB_STAGGER_SECONDS * i),
            coalesce=True,
            max_instances=1,
            misfire_grace_time=_JOB_MISFIRE_GRACE_SECONDS,
            jitter=_JOB_JITTER_SECONDS,
            **trigger_args,
        )

    register_backup_job_placeholder()
    scheduler.add_job(
        bootstrap_backup_job,
        "date",
        run_date=now + timedelta(seconds=_JOB_STAGGER_SECONDS * len(job_defs)),
        id="backup_bootstrap",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=_JOB_MISFIRE_GRACE_SECONDS,
    )

    _JOBS_REGISTERED = True
    logger.debug("%s Registered %s scheduled jobs (+ backup)", LogTag.SCHEDULER, len(job_defs))

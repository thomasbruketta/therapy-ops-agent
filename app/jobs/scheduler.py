"""Scheduler process for recurring jobs.

Run separately from CLI/manual flows using:
    python -m app.jobs.scheduler
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs.tasks import acorn_daily_send

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
JOB_ID = "acorn_daily_send"

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure process-wide logging for scheduler mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _log_job_state(scheduler: BlockingScheduler, event: JobExecutionEvent) -> None:
    """Log last and next run metadata for observability."""
    job = scheduler.get_job(event.job_id)
    job_next_run = getattr(job, "next_run_time", None) if job else None
    next_run = job_next_run.isoformat() if job_next_run else "none"
    last_run_at = (
        event.scheduled_run_time.astimezone(PACIFIC_TZ).isoformat()
        if event.scheduled_run_time
        else datetime.now(tz=PACIFIC_TZ).isoformat()
    )

    if event.exception:
        logger.exception(
            "Job %s failed at %s; next run at %s",
            event.job_id,
            last_run_at,
            next_run,
            exc_info=event.exception,
        )
        return

    logger.info("Job %s completed at %s; next run at %s", event.job_id, last_run_at, next_run)


def build_scheduler() -> BlockingScheduler:
    """Build and configure the scheduler instance."""
    scheduler = BlockingScheduler(timezone=PACIFIC_TZ)

    trigger = CronTrigger(hour=8, minute=0, timezone=PACIFIC_TZ)
    scheduler.add_job(
        acorn_daily_send,
        trigger=trigger,
        id=JOB_ID,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=1800,
    )

    scheduler.add_listener(
        lambda event: _log_job_state(scheduler, event),
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
    )

    next_run = trigger.get_next_fire_time(None, datetime.now(tz=PACIFIC_TZ))
    logger.info(
        "Registered %s for 08:00 %s (next run: %s)",
        JOB_ID,
        PACIFIC_TZ.key,
        next_run.isoformat() if next_run else "none",
    )

    return scheduler


def main() -> None:
    """Entrypoint for a dedicated scheduler process."""
    parser = argparse.ArgumentParser(description="Run the recurring job scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute acorn_daily_send immediately and exit (manual mode)",
    )
    args = parser.parse_args()

    configure_logging()

    if args.once:
        logger.info("Running in manual mode: executing %s once", JOB_ID)
        acorn_daily_send()
        logger.info("Manual execution of %s completed", JOB_ID)
        return

    scheduler = build_scheduler()
    logger.info("Starting scheduler process")
    scheduler.start()


if __name__ == "__main__":
    main()

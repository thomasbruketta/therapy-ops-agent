"""Task functions executed by the scheduler."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.jobs import acorn_daily_send as daily_send_job

logger = logging.getLogger(__name__)
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def acorn_daily_send() -> None:
    """Execute the daily Acorn send task in configured mode."""
    mode = os.getenv("ACORN_SCHEDULER_MODE", "dry-run").strip().lower()
    confirm_send = mode == "confirm-send"
    dry_run = not confirm_send
    target_date = datetime.now(tz=PACIFIC_TZ).date()

    logger.info("Running acorn_daily_send task in mode=%s for date=%s", mode, target_date.isoformat())
    result = daily_send_job.run(
        date=target_date,
        dry_run=dry_run,
        confirm_send=confirm_send,
        recipients_path=os.getenv("ACORN_RECIPIENTS_PATH", "state/acorn_recipients.json"),
        inline_recipients=[],
        recipient_source=os.getenv("ACORN_RECIPIENT_SOURCE", "simplepractice"),
    )
    logger.info(
        "acorn_daily_send run complete run_id=%s summary=%s triage=%s",
        result["run_id"],
        result["summary_path"],
        result["triage_path"],
    )

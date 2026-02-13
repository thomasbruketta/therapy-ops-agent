"""Task functions executed by the scheduler."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def acorn_daily_send() -> None:
    """Send the daily Acorn payload.

    Replace this implementation with the real send workflow.
    """
    logger.info("Running acorn_daily_send task")

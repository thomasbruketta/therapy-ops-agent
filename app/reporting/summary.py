"""Summary generation for triage reports."""

from __future__ import annotations

from collections import Counter
from typing import Any


def compute_summary(records: list[dict[str, Any]], total_appointments: int) -> dict[str, Any]:
    """Compute aggregate reporting stats from workflow records."""
    status_counts = Counter(record.get("status") for record in records)
    completed_attempts = status_counts.get("sent", 0) + status_counts.get("failed", 0)
    attempted_only = status_counts.get("attempted", 0)
    attempted_sends = completed_attempts or attempted_only

    skipped_reasons = Counter(
        record.get("reason", "unknown")
        for record in records
        if record.get("status") == "skipped"
    )
    failed_reasons = Counter(
        record.get("reason", "unknown")
        for record in records
        if record.get("status") == "failed"
    )

    return {
        "total_appointments": total_appointments,
        "attempted_sends": attempted_sends,
        "successful_sends": status_counts.get("sent", 0),
        "skipped": {
            "total": status_counts.get("skipped", 0),
            "reasons": dict(skipped_reasons),
        },
        "failed": {
            "total": status_counts.get("failed", 0),
            "reasons": dict(failed_reasons),
        },
    }

"""Task functions executed by the scheduler."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from app.domain.models import Appointment, ClientDetails, SendRequest
from app.orchestration.send import REQUIRED_FORM_TYPE, REQUIRED_MESSAGE_BODY, orchestrate_send
from app.utils.idempotency import IdempotencyStore
from app.workflows.dispatch import run_dispatch_workflow

logger = logging.getLogger(__name__)

SourceAppointment = dict[str, Any]
SourceLoader = Callable[[date], list[SourceAppointment]]
AcornSender = Callable[[SourceAppointment], bool]


@dataclass(slots=True)
class DailySendConfig:
    run_date: date
    dry_run: bool
    artifacts_dir: Path
    idempotency_store_path: Path


class DailySendError(RuntimeError):
    """Raised when mandatory runtime dependencies are unavailable."""


def _load_from_simplepractice(_run_date: date) -> list[SourceAppointment]:
    """Load appointments from source system.

    This placeholder intentionally returns an empty set until UI login/session
    wiring is configured for production.
    """
    logger.info("No source loader configured; returning zero appointments")
    return []


def _send_to_acorn(_appointment: SourceAppointment) -> bool:
    """Perform outbound side effect to Acorn.

    Placeholder stub for the actual Acorn adapter/API call.
    """
    return True


def _build_send_request(appointment: SourceAppointment, run_date: date) -> SendRequest:
    full_name = str(appointment.get("client_name") or "")
    name_parts = [part for part in full_name.split(" ") if part]

    return SendRequest(
        date=run_date.isoformat(),
        form_type=REQUIRED_FORM_TYPE,
        message_body=REQUIRED_MESSAGE_BODY,
        appointment=Appointment(
            appointment_id=str(appointment.get("appointment_id") or ""),
            scheduled_date=str(appointment.get("scheduled_date") or run_date.isoformat()),
            scheduled_time=str(appointment.get("scheduled_time") or ""),
            location=appointment.get("location"),
        ),
        client=ClientDetails(
            name_parts=name_parts,
            phone=appointment.get("phone"),
        ),
    )


def _resolve_config(*, run_date: date | None = None, dry_run: bool = True) -> DailySendConfig:
    tz = os.getenv("ACORN_TIMEZONE", "UTC")
    artifact_root = Path(os.getenv("ACORN_ARTIFACT_ROOT", "artifacts/runs"))
    idempotency_store_path = Path(
        os.getenv("ACORN_IDEMPOTENCY_STORE_PATH", "state/idempotency_sent_keys.json")
    )

    resolved_date = run_date or datetime.now(tz=UTC).date()
    logger.info(
        "Resolved job config (timezone=%s, run_date=%s, dry_run=%s)",
        tz,
        resolved_date.isoformat(),
        dry_run,
    )
    return DailySendConfig(
        run_date=resolved_date,
        dry_run=dry_run,
        artifacts_dir=artifact_root,
        idempotency_store_path=idempotency_store_path,
    )


def acorn_daily_send(
    *,
    run_date: date | None = None,
    dry_run: bool = True,
    source_loader: SourceLoader | None = None,
    acorn_sender: AcornSender | None = None,
) -> dict[str, Any]:
    """Run daily workflow with triage artifacts and optional send side effects."""
    config = _resolve_config(run_date=run_date, dry_run=dry_run)
    loader = source_loader or _load_from_simplepractice
    sender = acorn_sender or _send_to_acorn

    appointments = loader(config.run_date)
    logger.info("Loaded %s appointments for %s", len(appointments), config.run_date.isoformat())

    store = IdempotencyStore(path=config.idempotency_store_path)

    def _send_fn(appointment: SourceAppointment) -> bool:
        request = _build_send_request(appointment, config.run_date)
        result = orchestrate_send(request, idempotency_store=store)
        if not result.sent:
            codes = ",".join(issue.code for issue in result.triage_issues) or "validation_failed"
            raise DailySendError(codes)
        return sender(appointment)

    workflow_result = run_dispatch_workflow(
        appointments,
        send_fn=_send_fn,
        idempotency_key=f"acorn:{config.run_date.isoformat()}",
        dry_run=config.dry_run,
        artifacts_dir=str(config.artifacts_dir),
        report_date=config.run_date,
    )

    logger.info(
        "Workflow completed: attempted=%s successful=%s skipped=%s failed=%s triage_json=%s triage_md=%s",
        workflow_result["summary"]["attempted_sends"],
        workflow_result["summary"]["successful_sends"],
        workflow_result["summary"]["skipped"]["total"],
        workflow_result["summary"]["failed"]["total"],
        workflow_result["triage_json"],
        workflow_result["triage_md"],
    )
    return workflow_result

"""Appointment dispatch workflow with dry-run support and triage outputs."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from app.reporting.summary import compute_summary
from app.reporting.triage import write_triage_outputs
from app.utils.logging import get_structured_logger, log_workflow_event


SendFn = Callable[[dict[str, Any]], bool]


def run_dispatch_workflow(
    appointments: list[dict[str, Any]],
    *,
    send_fn: SendFn,
    idempotency_key: str,
    workflow_step: str = "appointment_dispatch",
    dry_run: bool = False,
    artifacts_dir: str = "artifacts",
    report_date: date | None = None,
) -> dict[str, Any]:
    """Run send triage workflow and write summary artifacts."""
    logger = get_structured_logger()
    records: list[dict[str, Any]] = []

    for appointment in appointments:
        client_name = appointment.get("client_name", "")
        record: dict[str, Any] = {
            "client_name": client_name,
            "idempotency_key": idempotency_key,
        }

        if dry_run:
            record.update({"status": "skipped", "reason": "dry_run"})
            log_workflow_event(
                logger,
                workflow_step=workflow_step,
                client_name=client_name,
                idempotency_key=idempotency_key,
                status="skipped",
                message="Dry-run: send skipped",
            )
            records.append(record)
            continue

        log_workflow_event(
            logger,
            workflow_step=workflow_step,
            client_name=client_name,
            idempotency_key=idempotency_key,
            status="attempted",
            message="Attempting send",
        )
        records.append({**record, "status": "attempted"})

        try:
            sent = send_fn(appointment)
            if sent:
                result = {**record, "status": "sent"}
                log_workflow_event(
                    logger,
                    workflow_step=workflow_step,
                    client_name=client_name,
                    idempotency_key=idempotency_key,
                    status="sent",
                    message="Send succeeded",
                )
            else:
                result = {**record, "status": "failed", "reason": "send_returned_false"}
                log_workflow_event(
                    logger,
                    workflow_step=workflow_step,
                    client_name=client_name,
                    idempotency_key=idempotency_key,
                    status="failed",
                    error_code="SEND_FALSE",
                    error_message="Sender returned false",
                    message="Send failed",
                )
        except Exception as exc:  # broad to ensure triage completeness
            result = {**record, "status": "failed", "reason": type(exc).__name__}
            log_workflow_event(
                logger,
                workflow_step=workflow_step,
                client_name=client_name,
                idempotency_key=idempotency_key,
                status="failed",
                error_code=type(exc).__name__.upper(),
                error_message=str(exc),
                message="Send raised exception",
            )

        records.append(result)

    summary = compute_summary(records, total_appointments=len(appointments))
    json_path, md_path = write_triage_outputs(
        artifacts_dir=artifacts_dir,
        summary=summary,
        records=records,
        report_date=report_date,
    )

    return {
        "summary": summary,
        "records": records,
        "triage_json": str(json_path),
        "triage_md": str(md_path),
    }

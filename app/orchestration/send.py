from __future__ import annotations

from app.domain.models import SendRequest, SendResult, TriageIssue
from app.utils.idempotency import IdempotencyStore, build_idempotency_key
from app.utils.identity import compute_client_id
from app.utils.phone import validate_phone

REQUIRED_FORM_TYPE = "v14"
REQUIRED_MESSAGE_BODY = "Please complete Acorn intake form v14 before your appointment."


def orchestrate_send(
    request: SendRequest,
    idempotency_store: IdempotencyStore | None = None,
) -> SendResult:
    store = idempotency_store or IdempotencyStore()
    issues: list[TriageIssue] = []

    if request.form_type != REQUIRED_FORM_TYPE:
        issues.append(
            TriageIssue(
                code="invalid_form_type",
                message="Form type must be exactly v14.",
                details={"form_type": request.form_type},
            )
        )

    if request.message_body != REQUIRED_MESSAGE_BODY:
        issues.append(
            TriageIssue(
                code="invalid_message_body",
                message="Message body does not match required text.",
            )
        )

    normalized_phone = validate_phone(request.client.phone)
    if not request.client.phone:
        issues.append(
            TriageIssue(
                code="missing_phone",
                message="Client phone is required before send.",
            )
        )
    elif not normalized_phone:
        issues.append(
            TriageIssue(
                code="invalid_phone",
                message="Client phone is not a valid E.164 phone number.",
                details={"phone": request.client.phone},
            )
        )

    client_id = compute_client_id(request.client.name_parts)
    idempotency_key = build_idempotency_key(request.date, client_id)
    if store.has_been_sent(idempotency_key):
        issues.append(
            TriageIssue(
                code="duplicate_send",
                message="Idempotency key has already been sent.",
                details={"idempotency_key": idempotency_key},
            )
        )

    if issues:
        return SendResult(
            sent=False,
            triage_issues=issues,
            idempotency_key=idempotency_key,
            normalized_phone=normalized_phone,
        )

    store.mark_sent(idempotency_key)
    return SendResult(
        sent=True,
        idempotency_key=idempotency_key,
        normalized_phone=normalized_phone,
    )

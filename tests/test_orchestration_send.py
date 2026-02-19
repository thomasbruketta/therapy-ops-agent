from __future__ import annotations

from app.domain.models import Appointment, ClientDetails, SendRequest
from app.orchestration.send import REQUIRED_MESSAGE_BODY, orchestrate_send
from app.utils.idempotency import IdempotencyStore


def _request(
    *,
    form_type: str = "v14",
    message_body: str = REQUIRED_MESSAGE_BODY,
    phone: str | None = "(555) 123-4567",
    name_parts: list[str] | None = None,
) -> SendRequest:
    return SendRequest(
        date="2026-02-19",
        form_type=form_type,
        message_body=message_body,
        appointment=Appointment(
            appointment_id="a1",
            scheduled_date="2026-02-19",
            scheduled_time="09:00",
        ),
        client=ClientDetails(
            name_parts=name_parts or ["Jane", "Q.", "Doe"],
            phone=phone,
        ),
    )


def test_orchestrate_send_success_marks_idempotency(tmp_path) -> None:
    store = IdempotencyStore(tmp_path / "idem.json")
    result = orchestrate_send(_request(), idempotency_store=store)
    assert result.sent is True
    assert result.idempotency_key is not None
    assert store.has_been_sent(result.idempotency_key)


def test_orchestrate_send_rejects_duplicate(tmp_path) -> None:
    store = IdempotencyStore(tmp_path / "idem.json")
    first = orchestrate_send(_request(), idempotency_store=store)
    second = orchestrate_send(_request(), idempotency_store=store)

    assert first.sent is True
    assert second.sent is False
    assert any(issue.code == "duplicate_send" for issue in second.triage_issues)


def test_orchestrate_send_flags_invalid_input(tmp_path) -> None:
    store = IdempotencyStore(tmp_path / "idem.json")
    result = orchestrate_send(
        _request(
            form_type="v13",
            message_body="bad message",
            phone="555-ABCD",
        ),
        idempotency_store=store,
    )

    assert result.sent is False
    codes = {issue.code for issue in result.triage_issues}
    assert "invalid_form_type" in codes
    assert "invalid_message_body" in codes
    assert "invalid_phone" in codes


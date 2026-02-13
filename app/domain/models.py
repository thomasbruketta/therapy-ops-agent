from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Appointment:
    appointment_id: str
    scheduled_date: str
    scheduled_time: str
    location: str | None = None


@dataclass(slots=True)
class ClientDetails:
    name_parts: list[str]
    phone: str | None = None


@dataclass(slots=True)
class SendRequest:
    date: str
    form_type: str
    message_body: str
    appointment: Appointment
    client: ClientDetails


@dataclass(slots=True)
class TriageIssue:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SendResult:
    sent: bool
    triage_issues: list[TriageIssue] = field(default_factory=list)
    idempotency_key: str | None = None
    normalized_phone: str | None = None

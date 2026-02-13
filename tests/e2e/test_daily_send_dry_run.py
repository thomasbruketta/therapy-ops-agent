from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.jobs.tasks import acorn_daily_send


@pytest.mark.e2e
def test_acorn_daily_send_dry_run_e2e(tmp_path: Path, monkeypatch) -> None:
    artifacts_dir = tmp_path / "artifacts"
    idempotency_path = tmp_path / "state" / "idempotency_sent_keys.json"
    monkeypatch.setenv("ACORN_ARTIFACT_ROOT", str(artifacts_dir))
    monkeypatch.setenv("ACORN_IDEMPOTENCY_STORE_PATH", str(idempotency_path))

    calls: list[str] = []

    def fake_source_loader(_run_date: date) -> list[dict[str, str]]:
        return [
            {
                "appointment_id": "appt-1",
                "scheduled_date": "2026-01-15",
                "scheduled_time": "09:00",
                "client_name": "Alice",
                "phone": "(555) 111-2222",
            },
            {
                "appointment_id": "appt-2",
                "scheduled_date": "2026-01-15",
                "scheduled_time": "09:30",
                "client_name": "Bob",
                "phone": "+15553334444",
            },
        ]

    def fake_acorn_sender(appointment: dict[str, str]) -> bool:
        calls.append(appointment["appointment_id"])
        return True

    result = acorn_daily_send(
        run_date=date(2026, 1, 15),
        dry_run=True,
        source_loader=fake_source_loader,
        acorn_sender=fake_acorn_sender,
    )

    assert calls == []
    assert result["summary"]["total_appointments"] == 2
    assert result["summary"]["attempted_sends"] == 0
    assert result["summary"]["successful_sends"] == 0
    assert result["summary"]["skipped"]["reasons"] == {"dry_run": 2}

    json_path = Path(result["triage_json"])
    md_path = Path(result["triage_md"])
    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["skipped"]["total"] == 2
    assert len(payload["records"]) == 2

    assert not idempotency_path.exists()

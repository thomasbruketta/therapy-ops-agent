from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.workflows.dispatch import run_dispatch_workflow


def test_dry_run_writes_triage_without_sending(tmp_path: Path) -> None:
    calls = []

    def fake_sender(_appointment):
        calls.append("called")
        return True

    appointments = [{"client_name": "Alice"}, {"client_name": "Bob"}]
    result = run_dispatch_workflow(
        appointments,
        send_fn=fake_sender,
        idempotency_key="idem-1",
        dry_run=True,
        artifacts_dir=tmp_path,
        report_date=date(2026, 1, 10),
    )

    assert calls == []
    assert result["summary"]["total_appointments"] == 2
    assert result["summary"]["attempted_sends"] == 0
    assert result["summary"]["successful_sends"] == 0
    assert result["summary"]["skipped"]["reasons"] == {"dry_run": 2}

    json_path = tmp_path / "triage_2026-01-10.json"
    md_path = tmp_path / "triage_2026-01-10.md"
    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text())
    assert payload["summary"]["skipped"]["total"] == 2
    assert len(payload["records"]) == 2
    assert payload["records"][0]["client_name"] == "A****"


def test_non_dry_run_attempts_send_and_tracks_failures(tmp_path: Path) -> None:
    sent_clients = []

    def fake_sender(appointment):
        if appointment["client_name"] == "Bob":
            raise RuntimeError("boom")
        sent_clients.append(appointment["client_name"])
        return True

    appointments = [{"client_name": "Alice"}, {"client_name": "Bob"}]
    result = run_dispatch_workflow(
        appointments,
        send_fn=fake_sender,
        idempotency_key="idem-2",
        dry_run=False,
        artifacts_dir=tmp_path,
        report_date=date(2026, 1, 11),
    )

    assert sent_clients == ["Alice"]
    assert result["summary"]["attempted_sends"] == 2
    assert result["summary"]["successful_sends"] == 1
    assert result["summary"]["failed"]["reasons"] == {"RuntimeError": 1}
    assert len(result["records"]) == 2
    assert result["records"][0]["client_name"] == "A****"

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import cli


def test_run_command_supports_runbook_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = {}

    def fake_run(*, date, dry_run, confirm_send):
        called["date"] = date
        called["dry_run"] = dry_run
        called["confirm_send"] = confirm_send

    monkeypatch.setattr(cli, "run_daily_send", fake_run)

    summary = tmp_path / "summary.json"
    triage = tmp_path / "triage.md"
    code = cli.main(
        [
            "run",
            "--mode",
            "confirm-send",
            "--since",
            "2026-02-13T00:00:00Z",
            "--window-minutes",
            "20",
            "--summary-out",
            str(summary),
            "--triage-out",
            str(triage),
            "--client-id",
            "CL-1",
            "--practitioner-id",
            "PR-1",
        ]
    )

    assert code == 0
    assert called["dry_run"] is False
    assert called["confirm_send"] is True
    assert summary.exists()
    assert triage.exists()
    assert json.loads(summary.read_text())["client_id"] == "CL-1"


def test_auth_simplepractice_requires_interactive_login(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["auth", "simplepractice", "--save-session", str(tmp_path / "session.json")])


def test_auth_simplepractice_writes_session_file(tmp_path: Path) -> None:
    session_file = tmp_path / "session.json"
    code = cli.main(
        [
            "auth",
            "simplepractice",
            "--interactive-login",
            "--save-session",
            str(session_file),
        ]
    )
    assert code == 0
    payload = json.loads(session_file.read_text())
    assert payload["provider"] == "simplepractice"

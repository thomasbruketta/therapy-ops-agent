from __future__ import annotations

import json
from pathlib import Path

from scripts.automation import run_daily_automation


class _SequenceRunner:
    def __init__(self, results):
        self.results = list(results)
        self.commands: list[list[str]] = []

    def __call__(self, command, cwd, env):
        self.commands.append(command)
        if not self.results:
            raise AssertionError(f"No fake result configured for command: {command}")
        return self.results.pop(0)


def _cmd(exit_code: int, stdout: str = "", stderr: str = "") -> run_daily_automation.CommandResult:
    return run_daily_automation.CommandResult(command=[], exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_ensure_docker_ready_starts_docker_when_initial_probe_fails() -> None:
    runner = _SequenceRunner([
        _cmd(1),
        _cmd(0),
        _cmd(0),
    ])

    ready, detail = run_daily_automation.ensure_docker_ready(
        timeout_sec=6,
        command_runner=runner,
        sleep_fn=lambda _: None,
    )

    assert ready is True
    assert "ready" in detail.lower()
    assert runner.commands[0][:2] == ["docker", "info"]
    assert runner.commands[1][:3] == ["open", "-a", "Docker"]


def test_execute_returns_needs_mfa_and_skips_send_when_preflight_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACORN_AUTOMATION_LOG_DIR", str(tmp_path / "logs"))

    runner = _SequenceRunner([
        _cmd(0),
        _cmd(2, stdout=json.dumps({"status": "MFA_REQUIRED", "message": "MFA needed"})),
    ])

    exit_code, report = run_daily_automation.execute(
        mode="send",
        target_date="2026-02-20",
        dry_run_send=False,
        report_to="",
        skip_email=True,
        timeout_sec=30,
        command_runner=runner,
        sleep_fn=lambda _: None,
    )

    assert exit_code == 2
    assert report["status"] == "NEEDS_MFA"
    assert all("app.jobs.acorn_daily_send" not in " ".join(cmd) for cmd in runner.commands)


def test_execute_send_success_records_totals_without_phi(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACORN_AUTOMATION_LOG_DIR", str(tmp_path / "logs"))

    send_payload = {
        "run_id": "abc",
        "totals": {"evaluated": 2, "eligible": 2, "sent_or_would_send": 2, "skipped": 0, "errors": 0},
        "summary_path": "/runtime/artifacts/runs/summary.json",
        "triage_path": "/runtime/artifacts/runs/triage.md",
        "full_name": "Jane Doe",
        "phone": "+15555550123",
    }
    runner = _SequenceRunner([
        _cmd(0),
        _cmd(0, stdout=json.dumps({"status": "AUTHENTICATED", "message": "ok"})),
        _cmd(0, stdout=json.dumps(send_payload)),
    ])

    exit_code, report = run_daily_automation.execute(
        mode="send",
        target_date="2026-02-20",
        dry_run_send=False,
        report_to="",
        skip_email=True,
        timeout_sec=30,
        command_runner=runner,
        sleep_fn=lambda _: None,
    )

    assert exit_code == 0
    assert report["status"] == "SUCCESS"
    assert report["send"]["totals"]["sent_or_would_send"] == 2
    assert "full_name" not in report["send"]
    assert "phone" not in report["send"]


def test_execute_send_failure_returns_failed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ACORN_AUTOMATION_LOG_DIR", str(tmp_path / "logs"))

    runner = _SequenceRunner([
        _cmd(0),
        _cmd(0, stdout=json.dumps({"status": "AUTHENTICATED", "message": "ok"})),
        _cmd(1, stdout="", stderr="send failed"),
    ])

    exit_code, report = run_daily_automation.execute(
        mode="send",
        target_date="2026-02-20",
        dry_run_send=False,
        report_to="",
        skip_email=True,
        timeout_sec=30,
        command_runner=runner,
        sleep_fn=lambda _: None,
    )

    assert exit_code == 1
    assert report["status"] == "FAILED"

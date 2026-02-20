from __future__ import annotations

import json
import sys
from datetime import date

from app.jobs import acorn_daily_send


class _FakeSendResult:
    def __init__(self) -> None:
        self.success = True
        self.context = {"ok": True}


class _FakeAcornAdapter:
    def __init__(self, page) -> None:
        self.page = page

    def login(self, username: str, password: str) -> None:
        return None

    def send_mobile_form(self, **kwargs):
        return _FakeSendResult()

    def verify_send_success(self, context) -> bool:
        return True


class _FakeContext:
    def new_page(self):
        return object()

    def close(self) -> None:
        return None


class _FakeBrowser:
    def new_context(self):
        return _FakeContext()

    def close(self) -> None:
        return None


class _FakePlaywright:
    chromium = type("_Chromium", (), {"launch": lambda self, headless: _FakeBrowser()})()


class _FakePlaywrightCM:
    def __enter__(self):
        return _FakePlaywright()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_run_returns_machine_readable_totals_for_dry_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ACORN_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ACORN_IDEMPOTENCY_STORE_PATH", str(tmp_path / "state.json"))

    result = acorn_daily_send.run(
        date=date(2026, 2, 20),
        dry_run=True,
        confirm_send=False,
        inline_recipients=["Jane Testuser|+15555550123"],
        recipient_source="recipients",
    )

    assert result["mode"] == "dry-run"
    assert result["date"] == "2026-02-20"
    assert result["totals"] == {
        "evaluated": 1,
        "eligible": 1,
        "sent_or_would_send": 1,
        "skipped": 0,
        "errors": 0,
    }


def test_run_returns_machine_readable_totals_for_confirm_send(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ACORN_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ACORN_IDEMPOTENCY_STORE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("ACORN_ENABLE_CONFIRM_SEND", "true")
    monkeypatch.setenv("ACORN_CLINICIAN_ID", "12345")
    monkeypatch.setenv("ACORN_USERNAME", "user")
    monkeypatch.setenv("ACORN_PASSWORD", "pass")

    import playwright.sync_api as sync_api

    monkeypatch.setattr(sync_api, "sync_playwright", lambda: _FakePlaywrightCM())

    from app.adapters import acorn_adapter_ui

    monkeypatch.setattr(acorn_adapter_ui, "AcornAdapterUI", _FakeAcornAdapter)

    result = acorn_daily_send.run(
        date=date(2026, 2, 20),
        dry_run=False,
        confirm_send=True,
        inline_recipients=["Jane Testuser|+15555550123"],
        recipient_source="recipients",
    )

    assert result["mode"] == "confirm-send"
    assert result["totals"] == {
        "evaluated": 1,
        "eligible": 1,
        "sent_or_would_send": 1,
        "skipped": 0,
        "errors": 0,
    }


def test_main_supports_json_and_human_output(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ACORN_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ACORN_IDEMPOTENCY_STORE_PATH", str(tmp_path / "state.json"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "acorn_daily_send",
            "--date",
            "2026-02-20",
            "--dry-run",
            "--source",
            "recipients",
            "--recipient",
            "Jane Testuser|+15555550123",
            "--json-output",
        ],
    )
    exit_code = acorn_daily_send.main()
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["mode"] == "dry-run"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "acorn_daily_send",
            "--date",
            "2026-02-20",
            "--dry-run",
            "--source",
            "recipients",
            "--recipient",
            "Jane Testuser|+15555550123",
        ],
    )
    exit_code = acorn_daily_send.main()
    assert exit_code == 0
    output = capsys.readouterr().out.strip()
    assert output.startswith("Run ")
    assert "summary=" in output and "triage=" in output

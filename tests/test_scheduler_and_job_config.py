from __future__ import annotations

from datetime import date
from pathlib import Path

from app.jobs import acorn_daily_send
from app.jobs import scheduler


def test_resolve_work_days_defaults_to_tue_fri(monkeypatch) -> None:
    monkeypatch.delenv("ACORN_WORK_DAYS", raising=False)
    monkeypatch.delenv("WORK_DAYS", raising=False)
    assert scheduler.resolve_work_days() == "tue,wed,thu,fri"


def test_resolve_work_days_uses_env_and_filters_invalid(monkeypatch) -> None:
    monkeypatch.setenv("ACORN_WORK_DAYS", "Tue,wed,garbage,thu")
    assert scheduler.resolve_work_days() == "tue,wed,thu"


def test_dry_run_writes_artifacts_and_does_not_require_playwright(
    tmp_path: Path,
    monkeypatch,
) -> None:
    recipients_path = tmp_path / "recipients.json"
    recipients_path.write_text(
        '[{"full_name":"Thomas Bruketta","phone":"+13108016045"}]',
        encoding="utf-8",
    )
    monkeypatch.setenv("ACORN_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ACORN_IDEMPOTENCY_STORE_PATH", str(tmp_path / "state.json"))

    result = acorn_daily_send.run(
        date=date(2026, 2, 13),
        dry_run=True,
        confirm_send=False,
        recipients_path=recipients_path,
        inline_recipients=[],
        recipient_source="recipients",
    )

    assert Path(result["summary_path"]).exists()
    assert Path(result["triage_path"]).exists()

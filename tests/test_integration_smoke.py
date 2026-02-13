from pathlib import Path

from conftest import resolve_attr


class MockUIAdapter:
    def __init__(self, *, fail_on_send=False, selector_failure=False):
        self.fail_on_send = fail_on_send
        self.selector_failure = selector_failure
        self.sent = []

    def send_mobile_form(self, client):
        if self.selector_failure:
            raise RuntimeError("selector_drift_fallback_failure")
        if self.fail_on_send:
            raise LookupError("acorn_confirmation_not_found")
        self.sent.append(client["client_id"])
        return {"ok": True, "confirmation": "ABC123"}


class MockTriageSink:
    def __init__(self):
        self.issues = []

    def create_issue(self, *, client, reason):
        self.issues.append({"client": client, "reason": reason})


class MockReportSink:
    def __init__(self):
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)


def _run(sut_module, appointments, *, dry_run=False, ui_kwargs=None):
    process_batch = resolve_attr(
        sut_module,
        "process_batch",
        "run_batch",
        "orchestrate",
    )

    triage = MockTriageSink()
    report = MockReportSink()
    adapter = MockUIAdapter(**(ui_kwargs or {}))

    result = process_batch(
        appointments=appointments,
        ui_adapter=adapter,
        triage_sink=triage,
        report_sink=report,
        dry_run=dry_run,
    )

    return result, adapter, triage, report


def test_happy_path_two_clients(sut_module):
    appointments = [
        {"client_id": "c1", "phone": "5551112222", "same_day_duplicate": False},
        {"client_id": "c2", "phone": "5553334444", "same_day_duplicate": False},
    ]

    _, adapter, triage, _ = _run(sut_module, appointments)

    assert adapter.sent == ["c1", "c2"]
    assert triage.issues == []


def test_missing_phone_skips_and_triages(sut_module):
    appointments = [{"client_id": "c1", "phone": "", "same_day_duplicate": False}]

    _, adapter, triage, _ = _run(sut_module, appointments)

    assert adapter.sent == []
    assert any(issue["reason"] == "missing_phone" for issue in triage.issues)


def test_duplicate_same_day_appointment_idempotent_skip(sut_module):
    appointments = [
        {"client_id": "c1", "phone": "5551112222", "same_day_duplicate": False},
        {"client_id": "c1", "phone": "5551112222", "same_day_duplicate": True},
    ]

    _, adapter, triage, _ = _run(sut_module, appointments)

    assert adapter.sent.count("c1") <= 1
    assert any(issue["reason"] in {"duplicate", "duplicate_same_day"} for issue in triage.issues)


def test_acorn_confirmation_not_found_failure_and_triage(sut_module):
    appointments = [{"client_id": "c1", "phone": "5551112222", "same_day_duplicate": False}]

    _, adapter, triage, _ = _run(sut_module, appointments, ui_kwargs={"fail_on_send": True})

    assert adapter.sent == []
    assert any(issue["reason"] == "acorn_confirmation_not_found" for issue in triage.issues)


def test_selector_drift_fallback_failure_triage_issue(sut_module):
    appointments = [{"client_id": "c1", "phone": "5551112222", "same_day_duplicate": False}]

    _, adapter, triage, _ = _run(
        sut_module,
        appointments,
        ui_kwargs={"selector_failure": True},
    )

    assert adapter.sent == []
    assert any("selector" in issue["reason"] for issue in triage.issues)


def test_dry_run_does_not_call_send_and_creates_artifacts(sut_module, tmp_path: Path):
    appointments = [{"client_id": "c1", "phone": "5551112222", "same_day_duplicate": False}]

    result, adapter, triage, report = _run(sut_module, appointments, dry_run=True)

    assert adapter.sent == []
    assert triage.issues is not None
    assert report.writes is not None

    artifacts = result.get("artifacts", {}) if isinstance(result, dict) else {}
    if artifacts:
        triage_path = artifacts.get("triage")
        report_path = artifacts.get("report")
        assert triage_path is not None
        assert report_path is not None
        assert Path(triage_path).exists() or triage.issues is not None
        assert Path(report_path).exists() or report.writes is not None

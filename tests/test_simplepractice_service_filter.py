from __future__ import annotations

from datetime import date

from app.adapters.simplepractice_adapter_ui import SimplePracticeAdapterUI


def _appointment(
    *,
    title: str | None = None,
    this_type: str | None = None,
    service_code: str | None = None,
    cpt_code: str | None = None,
    code: str | None = None,
) -> dict:
    attrs: dict[str, str] = {}
    if title is not None:
        attrs["title"] = title
    if this_type is not None:
        attrs["thisType"] = this_type
    if service_code is not None:
        attrs["serviceCode"] = service_code
    if cpt_code is not None:
        attrs["cptCode"] = cpt_code
    if code is not None:
        attrs["code"] = code
    return {"type": "appointments", "attributes": attrs, "relationships": {}}


def test_required_service_codes_defaults_to_90837(monkeypatch) -> None:
    monkeypatch.delenv("ACORN_REQUIRED_SERVICE_CODES", raising=False)
    assert SimplePracticeAdapterUI._required_service_codes() == {"90837"}


def test_required_service_codes_supports_csv(monkeypatch) -> None:
    monkeypatch.setenv("ACORN_REQUIRED_SERVICE_CODES", "90837, 90791")
    assert SimplePracticeAdapterUI._required_service_codes() == {"90837", "90791"}


def test_appointment_matches_when_90837_present_in_title() -> None:
    item = _appointment(title="90837 Psychotherapy 60 min")
    assert SimplePracticeAdapterUI._appointment_matches_service_codes(item, {"90837"}) is True


def test_appointment_matches_when_90837_present_in_this_type() -> None:
    item = _appointment(this_type="Service: 90837")
    assert SimplePracticeAdapterUI._appointment_matches_service_codes(item, {"90837"}) is True


def test_appointment_does_not_match_non_90837_service() -> None:
    item = _appointment(title="90791 Mental Health Assessment")
    assert SimplePracticeAdapterUI._appointment_matches_service_codes(item, {"90837"}) is False


def test_appointment_does_not_match_partial_numeric_token() -> None:
    item = _appointment(title="190837 follow-up")
    assert SimplePracticeAdapterUI._appointment_matches_service_codes(item, {"90837"}) is False


def test_fetch_daily_recipients_uses_schema_safe_fields_and_matches_this_type_code() -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.context = object()

    adapter = SimplePracticeAdapterUI(page=_FakePage())
    captured_appointments_fields: dict[str, str] = {}

    def _fake_frontend_get(path: str, params: dict[str, str]) -> dict:
        if path == "/frontend/appointments":
            captured_appointments_fields["value"] = params.get("fields[appointments]", "")
            return {
                "data": [
                    {
                        "type": "appointments",
                        "attributes": {
                            "title": "Jane Testuser",
                            "thisType": "Service: 90837",
                        },
                        "relationships": {
                            "client": {"data": {"type": "clients", "id": "c1"}},
                        },
                    }
                ]
            }
        if path == "/frontend/base-clients":
            return {
                "data": [
                    {
                        "id": "c1",
                        "attributes": {
                            "name": "Jane Testuser",
                            "defaultPhoneNumber": "+15555550123",
                        },
                    }
                ]
            }
        raise AssertionError(f"Unexpected path: {path}")

    adapter._frontend_get = _fake_frontend_get  # type: ignore[method-assign]
    recipients = adapter.fetch_daily_recipients(
        target_date=date(2026, 2, 20),
        clinician_id="123",
    )

    assert captured_appointments_fields["value"] == "client,title,startTime,endTime,thisType,clinicianId,attendanceStatus"
    assert recipients == [{"full_name": "Jane Testuser", "phone": "+15555550123"}]

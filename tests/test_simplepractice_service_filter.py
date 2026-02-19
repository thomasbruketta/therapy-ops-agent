from __future__ import annotations

from app.adapters.simplepractice_adapter_ui import SimplePracticeAdapterUI


def _appointment(*, title: str | None = None, this_type: str | None = None) -> dict:
    attrs: dict[str, str] = {}
    if title is not None:
        attrs["title"] = title
    if this_type is not None:
        attrs["thisType"] = this_type
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


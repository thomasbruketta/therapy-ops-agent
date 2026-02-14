from datetime import date, datetime

from conftest import resolve_attr


def test_client_id_normalization_including_punctuation_case(sut_module):
    normalize_client_id = resolve_attr(
        sut_module,
        "normalize_client_id",
        "client_id_normalize",
        "normalize_client_identifier",
    )

    assert normalize_client_id("Jane Q. Example") == "janeexample"


def test_phone_validation_and_normalization(sut_module):
    normalize_phone = resolve_attr(
        sut_module,
        "normalize_phone",
        "normalize_phone_number",
    )
    is_valid_phone = resolve_attr(
        sut_module,
        "is_valid_phone",
        "validate_phone",
        "phone_is_valid",
    )

    assert normalize_phone("(555) 123-4567") in {"+15551234567", "15551234567", "5551234567"}
    assert is_valid_phone("(555) 123-4567") is True
    assert is_valid_phone("555-ABCD") is False


def test_idempotency_key_generation_and_duplicate_detection(sut_module):
    make_idempotency_key = resolve_attr(
        sut_module,
        "make_idempotency_key",
        "generate_idempotency_key",
    )
    duplicate_detector_cls = resolve_attr(
        sut_module,
        "DuplicateDetector",
        "IdempotencyRegistry",
    )

    appt = {
        "client_name": "Jane Q. Example",
        "appointment_date": date(2026, 1, 1),
        "appointment_time": "09:00",
    }

    key_one = make_idempotency_key(appt)
    key_two = make_idempotency_key(appt)
    assert key_one == key_two

    detector = duplicate_detector_cls()
    check = getattr(detector, "is_duplicate", None)
    if check is None:
        check = getattr(detector, "seen", None)

    assert check is not None, "Duplicate detector must expose is_duplicate() or seen()"
    assert check(key_one) is False
    assert check(key_one) is True


def test_summary_aggregation_counters_and_reasons(sut_module):
    summary_cls = resolve_attr(
        sut_module,
        "SummaryAggregator",
        "RunSummary",
    )

    summary = summary_cls()

    record = getattr(summary, "record", None)
    if record is None:
        record = getattr(summary, "add", None)
    assert record is not None, "Summary aggregator must expose record() or add()"

    record("sent")
    record("skipped", reason="missing_phone")
    record("failed", reason="acorn_confirmation_not_found")

    export = getattr(summary, "as_dict", None)
    if export is None:
        export = getattr(summary, "to_dict", None)
    assert export is not None, "Summary aggregator must expose as_dict() or to_dict()"

    data = export()
    counters = data.get("counters", data)
    reasons = data.get("reasons", {})

    assert counters.get("sent", 0) >= 1
    assert counters.get("skipped", 0) >= 1
    assert counters.get("failed", 0) >= 1
    assert reasons.get("missing_phone", 0) >= 1
    assert reasons.get("acorn_confirmation_not_found", 0) >= 1

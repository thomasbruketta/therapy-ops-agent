from __future__ import annotations

from app.utils.identity import compute_client_id


def test_compute_client_id_uses_first_and_last_only() -> None:
    assert compute_client_id(["John", "C.", "Doe"]) == "johndoe"
    assert compute_client_id(["John", "Calvin", "Doe"]) == "johndoe"


def test_compute_client_id_preserves_hyphenated_last_name() -> None:
    assert compute_client_id(["DREW", "MICHAUD-GOETZ"]) == "drewmichaud-goetz"


def test_compute_client_id_preserves_hyphen_and_strips_other_punctuation() -> None:
    assert compute_client_id(["Mary-Kate", "O'Neil"]) == "mary-kateoneil"


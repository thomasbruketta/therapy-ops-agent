from __future__ import annotations

import re


def _normalize_name_component(value: str) -> str:
    """Normalize one name component for Acorn client_id usage.

    Keep only letters, numbers, and hyphens; drop all other punctuation.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9-]", "", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned.lower()


def compute_client_id(name_parts: list[str]) -> str:
    """Build a stable client id from name parts.

    Rules:
    - Use first and last name only (ignore middle initials/middle names)
    - lowercase
    - remove spaces
    - preserve hyphens
    - strip other punctuation/special chars
    """
    parts = [part for part in (name_parts or []) if isinstance(part, str) and part.strip()]
    if not parts:
        return ""

    first = _normalize_name_component(parts[0])
    if len(parts) == 1:
        return first

    last = _normalize_name_component(parts[-1])
    return f"{first}{last}"

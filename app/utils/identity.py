from __future__ import annotations

import re


def compute_client_id(name_parts: list[str]) -> str:
    """Build a stable client id from name parts.

    Rules:
    - lowercase
    - remove spaces
    - strip punctuation/special chars
    """
    merged = "".join(name_parts).lower()
    merged = merged.replace(" ", "")
    return re.sub(r"[^a-z0-9]", "", merged)

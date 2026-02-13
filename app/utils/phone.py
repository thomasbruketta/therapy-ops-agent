from __future__ import annotations

import re


def validate_phone(phone: str | None) -> str | None:
    """Return normalized E.164 phone if valid, else None.

    Basic normalization:
    - strip whitespace and punctuation
    - accept leading +
    - if missing + and 10 digits, assume +1
    - if missing + and 11-15 digits, prefix +
    """
    if not phone:
        return None

    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned)
        normalized = f"+{digits}"
    else:
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) == 10:
            normalized = f"+1{digits}"
        elif 11 <= len(digits) <= 15:
            normalized = f"+{digits}"
        else:
            return None

    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        return None

    return normalized

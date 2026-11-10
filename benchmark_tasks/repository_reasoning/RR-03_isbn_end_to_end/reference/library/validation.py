"""Validation helpers."""

from __future__ import annotations

from typing import Optional


class ValidationError(ValueError):
    pass


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value.strip()


def validate_year(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1450 <= value <= 2100:
        raise ValidationError("year must be an integer between 1450 and 2100")
    return value


def normalize_isbn(value: Optional[str]) -> Optional[str]:
    """Return the 13-digit form of an ISBN-13, or None. Raises ValidationError if invalid."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("isbn must be a string")
    digits = value.replace("-", "").replace(" ", "")
    if len(digits) != 13 or not digits.isdigit() or not digits.isascii():
        raise ValidationError("isbn must contain exactly 13 digits")
    checksum = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    if checksum % 10 != 0:
        raise ValidationError("isbn checksum is invalid")
    return digits

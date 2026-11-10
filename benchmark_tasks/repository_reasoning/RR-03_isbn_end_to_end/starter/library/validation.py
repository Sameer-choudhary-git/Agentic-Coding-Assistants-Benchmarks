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

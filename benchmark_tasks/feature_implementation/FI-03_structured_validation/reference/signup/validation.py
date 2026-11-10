"""Validation for user registration payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

FIELD_ORDER = ("username", "email", "age", "password", "password_confirm")

_USERNAME_CHARS = re.compile(r"[A-Za-z0-9_]+")
_EMAIL = re.compile(r"[A-Za-z0-9._+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}")


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str


@dataclass
class ValidationResult:
    ok: bool
    errors: List[FieldError] = field(default_factory=list)
    cleaned: Dict[str, Any] = field(default_factory=dict)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _check_username(value: Any, data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(value, str):
        return "invalid_type"
    value = value.strip()
    if len(value) < 3:
        return "too_short"
    if len(value) > 20:
        return "too_long"
    if not _USERNAME_CHARS.fullmatch(value):
        return "invalid_chars"
    if not value[0].isalpha():
        return "must_start_with_letter"
    return None


def _check_email(value: Any, data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(value, str):
        return "invalid_type"
    return None if _EMAIL.fullmatch(value.strip()) else "invalid_format"


def _check_age(value: Any, data: Dict[str, Any]) -> Optional[str]:
    if isinstance(value, bool) or not isinstance(value, int):
        return "invalid_type"
    if value < 13:
        return "too_young"
    if value > 120:
        return "out_of_range"
    return None


def _check_password(value: Any, data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(value, str):
        return "invalid_type"
    if len(value) < 8:
        return "too_short"
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        return "too_weak"
    return None


def _check_confirm(value: Any, data: Dict[str, Any]) -> Optional[str]:
    return None if value == data.get("password") else "mismatch"


_CHECKS: Dict[str, Callable[[Any, Dict[str, Any]], Optional[str]]] = {
    "username": _check_username,
    "email": _check_email,
    "age": _check_age,
    "password": _check_password,
    "password_confirm": _check_confirm,
}


def validate_registration(data: Dict[str, Any]) -> ValidationResult:
    """Validate a registration payload. See the task description for the full rule set."""
    errors: List[FieldError] = []
    for name in FIELD_ORDER:
        value = data.get(name)
        code = "required" if _missing(value) else _CHECKS[name](value, data)
        if code is not None:
            errors.append(FieldError(name, code))
    for key in sorted(k for k in data if k not in FIELD_ORDER):
        errors.append(FieldError(key, "unknown_field"))
    if errors:
        return ValidationResult(ok=False, errors=errors, cleaned={})
    cleaned = {name: data[name] for name in FIELD_ORDER if name != "password_confirm"}
    cleaned["username"] = cleaned["username"].strip().lower()
    cleaned["email"] = cleaned["email"].strip().lower()
    return ValidationResult(ok=True, errors=[], cleaned=cleaned)

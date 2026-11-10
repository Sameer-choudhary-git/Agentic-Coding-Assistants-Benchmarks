"""Validation for user registration payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

FIELD_ORDER = ("username", "email", "age", "password", "password_confirm")


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str


@dataclass
class ValidationResult:
    ok: bool
    errors: List[FieldError] = field(default_factory=list)
    cleaned: Dict[str, Any] = field(default_factory=dict)


def validate_registration(data: Dict[str, Any]) -> ValidationResult:
    """Validate a registration payload. See the task description for the full rule set."""
    raise NotImplementedError

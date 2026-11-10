"""Settings loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


@dataclass(frozen=True)
class Settings:
    audit_enabled: bool = True
    audit_include_names: bool = True


def parse_bool(text: str) -> bool:
    """Parse a boolean setting value (true/false/yes/no/on/off/1/0, case-insensitive)."""
    value = text.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"invalid boolean value: {text!r}")


def _read_pairs(text: str) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"invalid settings line: {raw!r}")
        pairs[key.strip()] = value.strip()
    return pairs


def parse_settings(text: str) -> Settings:
    pairs = _read_pairs(text)
    return Settings(
        audit_enabled=parse_bool(pairs.get("audit.enabled", "true")),
        audit_include_names=parse_bool(pairs.get("audit.include_names", "true")),
    )

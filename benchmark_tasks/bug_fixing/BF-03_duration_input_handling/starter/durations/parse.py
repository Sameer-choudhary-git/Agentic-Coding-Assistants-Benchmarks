"""Parse and format compact duration strings such as ``1d2h3m4s``."""

from __future__ import annotations

import re

_UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}
_COMPONENT = re.compile(r"(\d+)([dhms])")


def parse_duration(text: str) -> int:
    """Parse a compact duration string and return the total number of seconds.

    Grammar:
    * One or more components ``<digits><unit>`` where unit is ``d``, ``h``, ``m`` or ``s``.
    * Units appear in strictly descending order (``d`` > ``h`` > ``m`` > ``s``) and each unit at
      most once, e.g. ``"1d4h"``, ``"90s"``, ``"2h0m15s"``.
    * Units are case-insensitive. Leading and trailing whitespace is ignored; whitespace inside the
      string is not allowed.
    * Anything else (empty string, bare numbers, unknown units, repeated or out-of-order units,
      signs, decimals) raises ``ValueError``.
    * Non-string input raises ``TypeError``.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    total = 0
    for amount, unit in _COMPONENT.findall(text):
        total += int(amount) * _UNIT_SECONDS[unit]
    return total


def format_duration(seconds: int) -> str:
    """Format a non-negative number of seconds using the largest units first.

    ``0`` formats as ``"0s"``; zero-valued components are omitted otherwise.
    """
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    if seconds == 0:
        return "0s"
    parts = []
    for unit, size in _UNIT_SECONDS.items():
        value, seconds = divmod(seconds, size)
        if value:
            parts.append(f"{value}{unit}")
    return "".join(parts)

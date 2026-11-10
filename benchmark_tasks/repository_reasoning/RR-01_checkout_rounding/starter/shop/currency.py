"""Money helpers. All amounts are stored as integer minor units (cents)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Union

Number = Union[int, str, Decimal]


@dataclass(frozen=True, order=True)
class Money:
    cents: int

    @classmethod
    def from_decimal(cls, amount: Number) -> "Money":
        value = (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return cls(int(value))

    def __add__(self, other: "Money") -> "Money":
        return Money(self.cents + other.cents)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.cents - other.cents)

    def times(self, qty: int) -> "Money":
        return Money(self.cents * qty)

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        cents = abs(self.cents)
        return f"{sign}{cents // 100}.{cents % 100:02d}"


ZERO = Money(0)


def apply_percentage(amount: Money, percent: Number) -> Money:
    """Return ``amount * (1 - percent/100)`` rounded half-up to whole cents."""
    factor = Decimal(1) - Decimal(str(percent)) / Decimal(100)
    value = (Decimal(amount.cents) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return Money(int(value))


def total(amounts: Iterable[Money]) -> Money:
    result = ZERO
    for amount in amounts:
        result = result + amount
    return result

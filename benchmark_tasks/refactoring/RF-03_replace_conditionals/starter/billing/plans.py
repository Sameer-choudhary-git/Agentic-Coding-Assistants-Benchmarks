"""Subscription plan rules."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

CENT = Decimal("0.01")


def _check_seats(seats: int) -> None:
    if not isinstance(seats, int) or isinstance(seats, bool) or seats < 1:
        raise ValueError("seats must be a positive integer")


def seat_limit(plan: str) -> Optional[int]:
    if plan == "free":
        return 3
    elif plan == "team":
        return 50
    elif plan == "business":
        return 500
    elif plan == "enterprise":
        return None
    else:
        raise KeyError(plan)


def monthly_price(plan: str, seats: int, annual: bool = False) -> Decimal:
    _check_seats(seats)
    limit = seat_limit(plan)
    if limit is not None and seats > limit:
        raise ValueError(f"{plan} allows at most {limit} seats")
    if plan == "free":
        price = Decimal("0")
    elif plan == "team":
        price = Decimal("8") * seats
        if annual:
            price = price * Decimal("0.85")
    elif plan == "business":
        price = Decimal("15") * seats
        if seats > 100:
            price = Decimal("15") * 100 + Decimal("12") * (seats - 100)
        if annual:
            price = price * Decimal("0.80")
    elif plan == "enterprise":
        price = Decimal("2500") + Decimal("10") * max(0, seats - 200)
        if annual:
            price = price * Decimal("0.75")
    else:
        raise KeyError(plan)
    return price.quantize(CENT, rounding=ROUND_HALF_UP)


def can_upgrade(current: str, target: str) -> bool:
    if current == "free":
        current_rank = 0
    elif current == "team":
        current_rank = 1
    elif current == "business":
        current_rank = 2
    elif current == "enterprise":
        current_rank = 3
    else:
        raise KeyError(current)
    if target == "free":
        target_rank = 0
    elif target == "team":
        target_rank = 1
    elif target == "business":
        target_rank = 2
    elif target == "enterprise":
        target_rank = 3
    else:
        raise KeyError(target)
    return target_rank > current_rank

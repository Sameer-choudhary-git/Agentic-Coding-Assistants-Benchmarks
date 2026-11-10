"""Subscription plan rules implemented as a registry of Plan classes."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Optional, Type, Union

CENT = Decimal("0.01")


class UnknownPlanError(KeyError):
    """Raised when a plan name is not registered."""


class Plan:
    name: str = ""
    rank: int = 0
    annual_factor: Decimal = Decimal("1")

    def base_price(self, seats: int) -> Decimal:
        raise NotImplementedError

    def seat_limit(self) -> Optional[int]:
        return None

    def monthly_price(self, seats: int, annual: bool) -> Decimal:
        price = self.base_price(seats)
        if annual:
            price = price * self.annual_factor
        return price


_REGISTRY: Dict[str, Plan] = {}


def register_plan(plan: Union[Plan, Type[Plan]]) -> Plan:
    instance = plan() if isinstance(plan, type) else plan
    _REGISTRY[instance.name] = instance
    return instance


def get_plan(name: str) -> Plan:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownPlanError(name) from None


class FreePlan(Plan):
    name = "free"
    rank = 0

    def base_price(self, seats: int) -> Decimal:
        return Decimal("0")

    def seat_limit(self) -> Optional[int]:
        return 3


class TeamPlan(Plan):
    name = "team"
    rank = 1
    annual_factor = Decimal("0.85")

    def base_price(self, seats: int) -> Decimal:
        return Decimal("8") * seats

    def seat_limit(self) -> Optional[int]:
        return 50


class BusinessPlan(Plan):
    name = "business"
    rank = 2
    annual_factor = Decimal("0.80")

    def base_price(self, seats: int) -> Decimal:
        first = min(seats, 100)
        extra = max(0, seats - 100)
        return Decimal("15") * first + Decimal("12") * extra

    def seat_limit(self) -> Optional[int]:
        return 500


class EnterprisePlan(Plan):
    name = "enterprise"
    rank = 3
    annual_factor = Decimal("0.75")

    def base_price(self, seats: int) -> Decimal:
        return Decimal("2500") + Decimal("10") * max(0, seats - 200)


for _cls in (FreePlan, TeamPlan, BusinessPlan, EnterprisePlan):
    register_plan(_cls)


def _check_seats(seats: int) -> None:
    if not isinstance(seats, int) or isinstance(seats, bool) or seats < 1:
        raise ValueError("seats must be a positive integer")


def seat_limit(plan: str) -> Optional[int]:
    return get_plan(plan).seat_limit()


def monthly_price(plan: str, seats: int, annual: bool = False) -> Decimal:
    _check_seats(seats)
    selected = get_plan(plan)
    limit = selected.seat_limit()
    if limit is not None and seats > limit:
        raise ValueError(f"{plan} allows at most {limit} seats")
    return selected.monthly_price(seats, annual).quantize(CENT, rounding=ROUND_HALF_UP)


def can_upgrade(current: str, target: str) -> bool:
    return get_plan(target).rank > get_plan(current).rank

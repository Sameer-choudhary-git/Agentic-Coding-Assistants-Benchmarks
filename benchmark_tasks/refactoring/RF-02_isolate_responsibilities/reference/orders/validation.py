"""Order validation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

SUPPORTED_COUNTRIES = ("IN", "US", "DE")
KNOWN_COUPONS = ("WELCOME10", "BULK5")


class OrderError(ValueError):
    pass


def _validate_line(index: int, line: Dict[str, Any]) -> None:
    if not isinstance(line.get("sku"), str) or not line.get("sku"):
        raise OrderError(f"line {index}: sku is required")
    qty = line.get("qty")
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise OrderError(f"line {index}: qty must be a positive integer")
    price = line.get("unit_price")
    if not isinstance(price, str):
        raise OrderError(f"line {index}: unit_price must be a decimal string")
    try:
        negative = Decimal(price) < 0
    except ArithmeticError:
        raise OrderError(f"line {index}: unit_price must be a decimal string") from None
    if negative:
        raise OrderError(f"line {index}: unit_price must be non-negative")


def validate_order(order: Dict[str, Any]) -> None:
    if not isinstance(order, dict):
        raise OrderError("order must be a dict")
    order_id = order.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise OrderError("order id is required")
    country = order.get("country")
    if country not in SUPPORTED_COUNTRIES:
        raise OrderError(f"unsupported country: {country}")
    lines = order.get("lines")
    if not isinstance(lines, list) or not lines:
        raise OrderError("order must have at least one line")
    for index, line in enumerate(lines):
        _validate_line(index, line)
    coupon = order.get("coupon")
    if coupon is not None and coupon not in KNOWN_COUPONS:
        raise OrderError(f"unknown coupon: {coupon}")

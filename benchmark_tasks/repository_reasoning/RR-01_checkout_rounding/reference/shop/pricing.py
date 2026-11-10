"""Pricing rules."""

from __future__ import annotations

from typing import List

from shop.currency import Money, apply_percentage, total
from shop.models import CartLine

FREE_SHIPPING_FROM = Money(5000)
SHIPPING_FEE = Money(499)


def line_total(line: CartLine) -> Money:
    """Total for one cart line after the product discount, rounded half-up to cents."""
    return apply_percentage(line.product.price.times(line.qty), line.product.discount_percent)


def subtotal(lines: List[CartLine]) -> Money:
    return total(line_total(line) for line in lines)


def shipping(lines: List[CartLine]) -> Money:
    return Money(0) if subtotal(lines) >= FREE_SHIPPING_FROM else SHIPPING_FEE


def grand_total(lines: List[CartLine]) -> Money:
    return total([subtotal(lines), shipping(lines)])

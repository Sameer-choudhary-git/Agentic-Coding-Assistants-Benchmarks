"""Pricing rules."""

from __future__ import annotations

from typing import List

from shop.currency import Money, total
from shop.models import CartLine

FREE_SHIPPING_FROM = Money(5000)
SHIPPING_FEE = Money(499)


def line_total(line: CartLine) -> Money:
    """Total for one cart line after the product discount, rounded half-up to cents."""
    gross = line.product.price.cents * line.qty
    discounted = gross * (1 - line.product.discount_percent / 100)
    return Money(round(discounted))


def subtotal(lines: List[CartLine]) -> Money:
    exact = 0.0
    for line in lines:
        gross = line.product.price.cents * line.qty
        exact += gross * (1 - line.product.discount_percent / 100)
    return Money(int(exact))


def shipping(lines: List[CartLine]) -> Money:
    return Money(0) if subtotal(lines) >= FREE_SHIPPING_FROM else SHIPPING_FEE


def grand_total(lines: List[CartLine]) -> Money:
    return total([subtotal(lines), shipping(lines)])

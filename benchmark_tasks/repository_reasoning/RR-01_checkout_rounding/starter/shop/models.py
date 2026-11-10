"""Domain models."""

from __future__ import annotations

from dataclasses import dataclass

from shop.currency import Money


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: Money
    discount_percent: int = 0


@dataclass(frozen=True)
class CartLine:
    product: Product
    qty: int

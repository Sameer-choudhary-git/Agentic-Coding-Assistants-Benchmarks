"""Shopping cart."""

from __future__ import annotations

from typing import Dict, List

from shop.models import CartLine, Product


class Cart:
    def __init__(self) -> None:
        self._lines: Dict[str, CartLine] = {}

    def add(self, product: Product, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        existing = self._lines.get(product.sku)
        new_qty = qty + (existing.qty if existing else 0)
        self._lines[product.sku] = CartLine(product, new_qty)

    def lines(self) -> List[CartLine]:
        return [self._lines[sku] for sku in sorted(self._lines)]

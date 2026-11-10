"""Checkout: turns a cart into an invoice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from shop import pricing
from shop.cart import Cart
from shop.currency import Money


@dataclass(frozen=True)
class InvoiceLine:
    name: str
    qty: int
    amount: Money

    def render(self) -> str:
        return f"{self.name} x{self.qty}  {self.amount}"


@dataclass(frozen=True)
class Invoice:
    lines: List[InvoiceLine]
    shipping: Money
    total: Money

    def render(self) -> str:
        rows = [line.render() for line in self.lines]
        rows.append(f"Shipping  {self.shipping}")
        rows.append(f"Total  {self.total}")
        return "\n".join(rows)


def create_invoice(cart: Cart) -> Invoice:
    lines = cart.lines()
    invoice_lines = [InvoiceLine(l.product.name, l.qty, pricing.line_total(l)) for l in lines]
    return Invoice(lines=invoice_lines, shipping=pricing.shipping(lines), total=pricing.grand_total(lines))

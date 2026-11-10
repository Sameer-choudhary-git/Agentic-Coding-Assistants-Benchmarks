"""Order pricing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict

CENT = Decimal("0.01")
TAX_RATES = {"IN": Decimal("0.18"), "US": Decimal("0.07"), "DE": Decimal("0.19")}
COUPONS = {"WELCOME10": Decimal("0.10"), "BULK5": Decimal("0.05")}


@dataclass(frozen=True)
class PricedOrder:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(line: Dict[str, Any]) -> Decimal:
    return money(Decimal(line["unit_price"]) * line["qty"])


def price_order(order: Dict[str, Any]) -> PricedOrder:
    lines = order["lines"]
    subtotal = money(sum((Decimal(line["unit_price"]) * line["qty"] for line in lines), Decimal("0")))
    coupon = order.get("coupon")
    rate = COUPONS.get(coupon, Decimal("0"))
    if coupon == "BULK5" and sum(line["qty"] for line in lines) < 10:
        rate = Decimal("0")
    discount = money(subtotal * rate)
    taxable = subtotal - discount
    tax = money(taxable * TAX_RATES[order["country"]])
    return PricedOrder(subtotal=subtotal, discount=discount, tax=tax, total=taxable + tax)

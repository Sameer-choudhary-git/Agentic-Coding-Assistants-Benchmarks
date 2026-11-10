"""Order processing service."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict

CENT = Decimal("0.01")
TAX_RATES = {"IN": Decimal("0.18"), "US": Decimal("0.07"), "DE": Decimal("0.19")}
COUPONS = {"WELCOME10": Decimal("0.10"), "BULK5": Decimal("0.05")}


class OrderError(ValueError):
    pass


def process_order(order: Dict[str, Any]) -> str:
    # --- validation ---
    if not isinstance(order, dict):
        raise OrderError("order must be a dict")
    order_id = order.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise OrderError("order id is required")
    country = order.get("country")
    if country not in TAX_RATES:
        raise OrderError(f"unsupported country: {country}")
    lines = order.get("lines")
    if not isinstance(lines, list) or not lines:
        raise OrderError("order must have at least one line")
    for index, line in enumerate(lines):
        if not isinstance(line.get("sku"), str) or not line.get("sku"):
            raise OrderError(f"line {index}: sku is required")
        qty = line.get("qty")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise OrderError(f"line {index}: qty must be a positive integer")
        price = line.get("unit_price")
        if not isinstance(price, str):
            raise OrderError(f"line {index}: unit_price must be a decimal string")
        try:
            if Decimal(price) < 0:
                raise OrderError(f"line {index}: unit_price must be non-negative")
        except ArithmeticError:
            raise OrderError(f"line {index}: unit_price must be a decimal string") from None
    coupon = order.get("coupon")
    if coupon is not None and coupon not in COUPONS:
        raise OrderError(f"unknown coupon: {coupon}")

    # --- pricing ---
    subtotal = Decimal("0")
    for line in lines:
        subtotal += Decimal(line["unit_price"]) * line["qty"]
    subtotal = subtotal.quantize(CENT, rounding=ROUND_HALF_UP)
    rate = COUPONS.get(coupon, Decimal("0"))
    total_qty = sum(line["qty"] for line in lines)
    if coupon == "BULK5" and total_qty < 10:
        rate = Decimal("0")
    discount = (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    taxable = subtotal - discount
    tax = (taxable * TAX_RATES[country]).quantize(CENT, rounding=ROUND_HALF_UP)
    total = taxable + tax

    # --- receipt ---
    out = [f"Order {order_id} ({country})"]
    for line in lines:
        line_total = (Decimal(line["unit_price"]) * line["qty"]).quantize(CENT, rounding=ROUND_HALF_UP)
        out.append(f"  {line['sku']:<10} x{line['qty']:>3}  {line_total:>10}")
    out.append(f"  {'Subtotal':<15}{subtotal:>10}")
    if discount:
        out.append(f"  {'Discount':<15}{-discount:>10}")
    out.append(f"  {'Tax':<15}{tax:>10}")
    out.append(f"  {'Total':<15}{total:>10}")
    return "\n".join(out)

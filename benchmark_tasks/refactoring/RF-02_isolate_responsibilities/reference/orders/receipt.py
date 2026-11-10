"""Receipt rendering."""

from __future__ import annotations

from typing import Any, Dict

from orders.pricing import PricedOrder, line_total


def format_receipt(order: Dict[str, Any], priced: PricedOrder) -> str:
    out = [f"Order {order['id']} ({order['country']})"]
    for line in order["lines"]:
        out.append(f"  {line['sku']:<10} x{line['qty']:>3}  {line_total(line):>10}")
    out.append(f"  {'Subtotal':<15}{priced.subtotal:>10}")
    if priced.discount:
        out.append(f"  {'Discount':<15}{-priced.discount:>10}")
    out.append(f"  {'Tax':<15}{priced.tax:>10}")
    out.append(f"  {'Total':<15}{priced.total:>10}")
    return "\n".join(out)

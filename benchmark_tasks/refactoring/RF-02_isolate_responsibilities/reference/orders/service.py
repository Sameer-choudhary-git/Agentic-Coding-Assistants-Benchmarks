"""Order processing service (orchestration only)."""

from __future__ import annotations

from typing import Any, Dict

from orders.pricing import price_order
from orders.receipt import format_receipt
from orders.validation import OrderError, validate_order

__all__ = ["OrderError", "process_order"]


def process_order(order: Dict[str, Any]) -> str:
    """Validate, price and render an order."""
    validate_order(order)
    priced = price_order(order)
    return format_receipt(order, priced)

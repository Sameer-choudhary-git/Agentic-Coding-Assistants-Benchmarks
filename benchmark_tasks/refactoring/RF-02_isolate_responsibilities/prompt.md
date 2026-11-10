# Task RF-02: Isolate responsibilities in the order service

`orders/service.py` contains one large function, `process_order(order: dict) -> str`, that validates an
order, computes prices and formats a receipt. Refactor it into separate modules **without changing
behaviour**.

Create these modules and functions:

| Module | Function | Contract |
|---|---|---|
| `orders/validation.py` | `validate_order(order: dict) -> None` | Raises `OrderError` with exactly the same messages as today for invalid orders; returns `None` otherwise. Define `OrderError` here. |
| `orders/pricing.py` | `price_order(order: dict) -> PricedOrder` | `PricedOrder` is a frozen dataclass defined in `pricing.py` with fields `subtotal`, `discount`, `tax`, `total` (all `Decimal`, quantised to `0.01` exactly as the current code does). Assumes the order is valid. |
| `orders/receipt.py` | `format_receipt(order: dict, priced: PricedOrder) -> str` | Returns exactly the receipt string the current code produces. |
| `orders/service.py` | `process_order(order: dict) -> str` | Orchestration only: calls `validate_order`, `price_order` and `format_receipt` and returns the receipt. At most 6 statements in its body (docstring excluded). |

Dependency rules:
- `validation.py` must not import `pricing`, `receipt` or `service`.
- `pricing.py` must not import `receipt` or `service`.
- `OrderError` must still be importable as `from orders.service import OrderError` and `from orders import OrderError`.

The output of `process_order` must remain byte-for-byte identical for every input, and invalid orders must
raise `OrderError` with identical messages. Standard library only; you may add tests under `tests/`.

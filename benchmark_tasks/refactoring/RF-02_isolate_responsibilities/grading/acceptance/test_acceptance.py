import ast
import importlib
import inspect
from decimal import Decimal

import pytest

import orders
from orders.service import OrderError, process_order

ORDERS = [
    {
        "id": "A-1",
        "country": "IN",
        "lines": [
            {
                "sku": "PEN",
                "qty": 3,
                "unit_price": "10.505"
            },
            {
                "sku": "BOOK",
                "qty": 1,
                "unit_price": "299.99"
            }
        ]
    },
    {
        "id": "B-2",
        "country": "US",
        "coupon": "WELCOME10",
        "lines": [
            {
                "sku": "MUG",
                "qty": 2,
                "unit_price": "7.25"
            }
        ]
    },
    {
        "id": "C-3",
        "country": "DE",
        "coupon": "BULK5",
        "lines": [
            {
                "sku": "BOLT",
                "qty": 9,
                "unit_price": "0.333"
            }
        ]
    },
    {
        "id": "D-4",
        "country": "DE",
        "coupon": "BULK5",
        "lines": [
            {
                "sku": "BOLT",
                "qty": 9,
                "unit_price": "0.333"
            },
            {
                "sku": "NUT",
                "qty": 1,
                "unit_price": "0.10"
            }
        ]
    },
    {
        "id": "E-5",
        "country": "US",
        "lines": [
            {
                "sku": "FREEBIE",
                "qty": 1,
                "unit_price": "0"
            }
        ]
    }
]

GOLDEN = [
    "Order A-1 (IN)\n  PEN        x  3       31.52\n  BOOK       x  1      299.99\n  Subtotal           331.51\n  Tax                 59.67\n  Total              391.18",
    "Order B-2 (US)\n  MUG        x  2       14.50\n  Subtotal            14.50\n  Discount            -1.45\n  Tax                  0.91\n  Total               13.96",
    "Order C-3 (DE)\n  BOLT       x  9        3.00\n  Subtotal             3.00\n  Tax                  0.57\n  Total                3.57",
    "Order D-4 (DE)\n  BOLT       x  9        3.00\n  NUT        x  1        0.10\n  Subtotal             3.10\n  Discount            -0.16\n  Tax                  0.56\n  Total                3.50",
    "Order E-5 (US)\n  FREEBIE    x  1        0.00\n  Subtotal             0.00\n  Tax                  0.00\n  Total                0.00"
]

BAD_ORDERS = [
    "not a dict",
    {
        "country": "US",
        "lines": []
    },
    {
        "id": "X",
        "country": "FR",
        "lines": []
    },
    {
        "id": "X",
        "country": "US",
        "lines": []
    },
    {
        "id": "X",
        "country": "US",
        "lines": [
            {
                "qty": 1,
                "unit_price": "1"
            }
        ]
    },
    {
        "id": "X",
        "country": "US",
        "lines": [
            {
                "sku": "A",
                "qty": True,
                "unit_price": "1"
            }
        ]
    },
    {
        "id": "X",
        "country": "US",
        "lines": [
            {
                "sku": "A",
                "qty": 1,
                "unit_price": 1.5
            }
        ]
    },
    {
        "id": "X",
        "country": "US",
        "lines": [
            {
                "sku": "A",
                "qty": 1,
                "unit_price": "abc"
            }
        ]
    },
    {
        "id": "X",
        "country": "US",
        "lines": [
            {
                "sku": "A",
                "qty": 1,
                "unit_price": "-1"
            }
        ]
    },
    {
        "id": "X",
        "country": "US",
        "coupon": "FREE",
        "lines": [
            {
                "sku": "A",
                "qty": 1,
                "unit_price": "1"
            }
        ]
    }
]

BAD_MESSAGES = [
    "order must be a dict",
    "order id is required",
    "unsupported country: FR",
    "order must have at least one line",
    "line 0: sku is required",
    "line 0: qty must be a positive integer",
    "line 0: unit_price must be a decimal string",
    "line 0: unit_price must be a decimal string",
    "line 0: unit_price must be non-negative",
    "unknown coupon: FREE"
]


def load(name):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        pytest.fail(f"module {name} cannot be imported: {exc}")


@pytest.mark.parametrize("index", range(len(ORDERS)))
def test_process_order_golden(index):
    assert process_order(ORDERS[index]) == GOLDEN[index]


@pytest.mark.parametrize("index", range(len(BAD_ORDERS)))
def test_validation_errors_preserved(index):
    with pytest.raises(OrderError) as info:
        process_order(BAD_ORDERS[index])
    assert str(info.value) == BAD_MESSAGES[index]


def test_validate_order_interface():
    validation = load("orders.validation")
    assert validation.validate_order(ORDERS[0]) is None
    with pytest.raises(validation.OrderError):
        validation.validate_order(BAD_ORDERS[2])
    assert validation.OrderError is OrderError
    assert orders.OrderError is OrderError


def test_price_order_interface():
    pricing = load("orders.pricing")
    priced = pricing.price_order(ORDERS[3])
    assert isinstance(priced, pricing.PricedOrder)
    assert (priced.subtotal, priced.discount, priced.tax, priced.total) == (
        Decimal("3.10"), Decimal("0.16"), Decimal("0.56"), Decimal("3.50"))
    assert all(isinstance(v, Decimal) for v in (priced.subtotal, priced.discount, priced.tax, priced.total))
    with pytest.raises(Exception):
        priced.total = Decimal("0")


def test_format_receipt_interface():
    pricing = load("orders.pricing")
    receipt = load("orders.receipt")
    priced = pricing.price_order(ORDERS[1])
    assert receipt.format_receipt(ORDERS[1], priced) == GOLDEN[1]
    fake = pricing.PricedOrder(Decimal("1.00"), Decimal("0.00"), Decimal("0.10"), Decimal("1.10"))
    text = receipt.format_receipt(ORDERS[4], fake)
    assert text.splitlines()[-1] == "  Total                1.10"


def imported_modules(module_name):
    module = load(module_name)
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize(
    "module,forbidden",
    [("orders.validation", ["pricing", "receipt", "service"]), ("orders.pricing", ["receipt", "service"])],
)
def test_dependency_rules(module, forbidden):
    names = imported_modules(module)
    for bad in forbidden:
        offenders = [n for n in names if n.split(".")[-1] == bad or f".{bad}." in f".{n}."]
        assert not offenders, f"{module} imports {offenders}"


def test_service_is_thin():
    import orders.service as service

    tree = ast.parse(inspect.getsource(service))
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_order")
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        body = body[1:]
    assert len(body) <= 6, f"process_order has {len(body)} statements"
    called = {n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
              for n in ast.walk(func) if isinstance(n, ast.Call)}
    assert {"validate_order", "price_order", "format_receipt"} <= called

from orders import OrderError, process_order


def test_simple_order_receipt():
    order = {"id": "R1", "country": "US", "lines": [{"sku": "A", "qty": 2, "unit_price": "1.50"}]}
    assert process_order(order) == (
        "Order R1 (US)\n  A          x  2        3.00\n  Subtotal             3.00\n"
        "  Tax                  0.21\n  Total                3.21"
    )


def test_order_error_is_value_error():
    assert issubclass(OrderError, ValueError)

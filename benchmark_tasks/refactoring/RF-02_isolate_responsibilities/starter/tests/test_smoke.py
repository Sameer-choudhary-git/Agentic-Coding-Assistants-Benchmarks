from orders import process_order


def test_basic():
    order = {"id": "A1", "country": "US", "lines": [{"sku": "X", "qty": 1, "unit_price": "1.00"}]}
    assert process_order(order).startswith("Order A1 (US)")

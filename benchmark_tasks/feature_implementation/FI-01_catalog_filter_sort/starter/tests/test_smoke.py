from catalog import Product, filter_by_category


def test_filter_by_category():
    p = Product(1, "Pen", "Office", 1.0, 4.0, 3)
    assert filter_by_category([p], "office") == [p]

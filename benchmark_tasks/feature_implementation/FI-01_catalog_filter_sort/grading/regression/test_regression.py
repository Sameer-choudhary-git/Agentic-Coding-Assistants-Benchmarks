from catalog import Product, filter_by_category


def test_filter_by_category_unchanged():
    a = Product(1, "A", "Books", 1.0, 1.0, 1)
    b = Product(2, "B", "books", 1.0, 1.0, 1)
    c = Product(3, "C", "Toys", 1.0, 1.0, 1)
    assert filter_by_category([a, b, c], "BOOKS") == [a, b]


def test_product_is_frozen():
    import dataclasses

    p = Product(1, "A", "Books", 1.0, 1.0, 1)
    try:
        p.price = 2.0
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Product must stay frozen")

import pytest

from catalog import Product, search_products

P = [
    Product(5, "banana stand", "Garden", 30.0, 4.5, 0),
    Product(2, "Apple Peeler", "Kitchen", 12.5, 4.5, 10),
    Product(9, "Cherry Pitter", "kitchen", 12.5, 3.9, 2),
    Product(1, "apple corer", "KITCHEN", 8.0, 4.8, 0),
    Product(7, "Dish Rack", "Kitchen", 25.0, 4.1, 5),
    Product(3, "Easel", "Art", 60.0, 4.5, 1),
]


def ids(products):
    return [p.id for p in products]


def test_no_filters_sorted_by_name():
    assert ids(search_products(P)) == [1, 2, 5, 9, 7, 3]


def test_category_filter_case_insensitive():
    assert ids(search_products(P, category="kitchen")) == [1, 2, 9, 7]


def test_price_range_inclusive():
    assert ids(search_products(P, min_price=12.5, max_price=30.0, sort_by="price")) == [2, 9, 7, 5]


def test_in_stock_filter():
    assert ids(search_products(P, in_stock=True)) == [2, 9, 7, 3]
    assert ids(search_products(P, in_stock=False)) == [1, 5]


def test_sort_price_descending_with_tiebreak():
    assert ids(search_products(P, sort_by="price", descending=True)) == [3, 5, 7, 2, 9, 1]


def test_sort_rating():
    assert ids(search_products(P, sort_by="rating")) == [9, 7, 2, 3, 5, 1]
    assert ids(search_products(P, sort_by="rating", descending=True)) == [1, 2, 3, 5, 7, 9]


@pytest.mark.parametrize(
    "kwargs",
    [{"sort_by": "stock"}, {"min_price": -1}, {"max_price": -0.01}, {"min_price": 10, "max_price": 5}],
)
def test_validation_errors(kwargs):
    with pytest.raises(ValueError):
        search_products(P, **kwargs)


def test_input_not_mutated():
    original = list(P)
    result = search_products(P, sort_by="price")
    assert P == original
    assert result is not P

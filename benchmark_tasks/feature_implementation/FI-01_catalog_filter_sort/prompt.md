# Task FI-01: Implement catalog filtering and sorting

The module `catalog/query.py` contains a `Product` dataclass, a working `filter_by_category()` helper,
and a stub `search_products()` that raises `NotImplementedError`.

Implement `search_products()` exactly as specified in its docstring:

```python
def search_products(products, *, category=None, min_price=None, max_price=None,
                    in_stock=None, sort_by="name", descending=False) -> list[Product]
```

Requirements (also in the docstring):
1. All filters are optional and combined with AND.
   - `category`: exact match, case-insensitive.
   - `min_price` / `max_price`: inclusive bounds on `price`.
   - `in_stock=True` keeps products with `stock > 0`; `in_stock=False` keeps products with `stock == 0`.
2. `sort_by` must be `"name"`, `"price"` or `"rating"`. Name sorting is case-insensitive.
3. `descending=True` reverses the primary sort key only; ties are always broken by `id` ascending.
4. Raise `ValueError` for an unknown `sort_by`, a negative `min_price`/`max_price`, or `min_price > max_price`.
5. Do not mutate the input list; return a new list.

Constraints: do not change `Product` or `filter_by_category()`; no third-party dependencies; you may add tests under `tests/`.

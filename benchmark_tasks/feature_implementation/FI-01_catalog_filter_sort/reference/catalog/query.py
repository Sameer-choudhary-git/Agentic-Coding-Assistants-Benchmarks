"""Querying helpers for an in-memory product catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category: str
    price: float
    rating: float
    stock: int


def filter_by_category(products: Iterable[Product], category: str) -> List[Product]:
    """Return products whose category equals ``category`` (case-insensitive)."""
    wanted = category.casefold()
    return [p for p in products if p.category.casefold() == wanted]


_SORT_KEYS = {
    "name": lambda p: p.name.casefold(),
    "price": lambda p: p.price,
    "rating": lambda p: p.rating,
}


def search_products(
    products: List[Product],
    *,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    sort_by: str = "name",
    descending: bool = False,
) -> List[Product]:
    """Filter and sort products.

    * Filters are optional and combined with AND: ``category`` (case-insensitive exact match),
      ``min_price``/``max_price`` (inclusive), ``in_stock`` (True: stock > 0, False: stock == 0).
    * ``sort_by`` is ``"name"`` (case-insensitive), ``"price"`` or ``"rating"``.
    * ``descending`` reverses the primary key only; ties are broken by ``id`` ascending.
    * ``ValueError`` for unknown ``sort_by``, negative price bounds or ``min_price > max_price``.
    * The input list is not mutated; a new list is returned.
    """
    if sort_by not in _SORT_KEYS:
        raise ValueError(f"unknown sort_by: {sort_by!r}")
    for bound in (min_price, max_price):
        if bound is not None and bound < 0:
            raise ValueError("price bounds must be non-negative")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price must not exceed max_price")

    result = list(products)
    if category is not None:
        result = filter_by_category(result, category)
    if min_price is not None:
        result = [p for p in result if p.price >= min_price]
    if max_price is not None:
        result = [p for p in result if p.price <= max_price]
    if in_stock is not None:
        result = [p for p in result if (p.stock > 0) == in_stock]

    key = _SORT_KEYS[sort_by]
    result.sort(key=lambda p: p.id)
    result.sort(key=key, reverse=descending)
    return result

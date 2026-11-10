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
    raise NotImplementedError

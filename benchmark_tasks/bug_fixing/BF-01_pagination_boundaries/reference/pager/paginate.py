"""Simple list pagination helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: List[T]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


def paginate(items: Sequence[T], page: int, per_page: int) -> Page[T]:
    """Return one page of ``items``.

    Contract:
    * ``page`` is 1-indexed: page 1 contains ``items[0:per_page]``.
    * ``total_pages`` is ``ceil(len(items) / per_page)``; an empty sequence has 0 pages.
    * Page 1 of an empty sequence is valid and returns an empty ``items`` list.
    * Any other ``page`` outside ``1..total_pages`` raises ``ValueError``.
    * ``per_page`` must be >= 1, otherwise ``ValueError`` is raised.
    * ``has_next`` is True only if ``page < total_pages``.
    * ``has_prev`` is True only if ``page > 1``.
    """
    if per_page < 1:
        raise ValueError("per_page must be >= 1")
    total_items = len(items)
    total_pages = -(-total_items // per_page)
    if page < 1:
        raise ValueError(f"page {page} out of range")
    if total_pages == 0:
        if page != 1:
            raise ValueError(f"page {page} out of range")
    elif page > total_pages:
        raise ValueError(f"page {page} out of range")
    start = (page - 1) * per_page
    end = start + per_page
    return Page(
        items=list(items[start:end]),
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

"""Library domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Book:
    id: int
    title: str
    author: str
    year: Optional[int] = None


@dataclass
class Library:
    books: Dict[int, Book] = field(default_factory=dict)
    next_id: int = 1

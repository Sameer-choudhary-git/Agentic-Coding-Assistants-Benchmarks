"""Inventory ledger with stock reservations."""

from __future__ import annotations

from typing import Dict, List, Tuple


class InventoryError(Exception):
    """Base class for ledger errors."""


class UnknownSku(InventoryError, KeyError):
    """Raised when an operation references a SKU that was never received."""


class InsufficientStock(InventoryError):
    """Raised when an operation needs more units than are available."""


class Ledger:
    """Tracks on-hand and reserved quantities per SKU.

    * ``on_hand(sku)``: physical units in stock.
    * ``reserved(sku)``: units promised to orders but not yet shipped.
    * ``available(sku) == on_hand(sku) - reserved(sku)`` is always >= 0.
    * Quantities passed to any method must be positive ``int`` values (``bool`` is rejected);
      otherwise ``ValueError`` is raised.
    * Every successful mutating call appends ``(operation, sku, qty)`` to ``history``.
    """

    def __init__(self) -> None:
        self._on_hand: Dict[str, int] = {}
        self._reserved: Dict[str, int] = {}
        self.history: List[Tuple[str, str, int]] = []

    @staticmethod
    def _check_qty(qty: int) -> None:
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            raise ValueError("quantity must be a positive integer")

    def _require(self, sku: str) -> None:
        if sku not in self._on_hand:
            raise UnknownSku(sku)

    def receive(self, sku: str, qty: int) -> None:
        """Add ``qty`` units of ``sku`` to stock (creates the SKU if needed)."""
        self._check_qty(qty)
        self._on_hand[sku] = self._on_hand.get(sku, 0) + qty
        self._reserved.setdefault(sku, 0)
        self.history.append(("receive", sku, qty))

    def on_hand(self, sku: str) -> int:
        self._require(sku)
        return self._on_hand[sku]

    def reserved(self, sku: str) -> int:
        self._require(sku)
        return self._reserved[sku]

    def available(self, sku: str) -> int:
        self._require(sku)
        return self._on_hand[sku] - self._reserved[sku]

    def reserve(self, sku: str, qty: int) -> None:
        """Reserve ``qty`` available units. Raises ``InsufficientStock`` if fewer are available."""
        self._check_qty(qty)
        self._require(sku)
        if qty > self.available(sku):
            raise InsufficientStock(f"{sku}: requested {qty}, available {self.available(sku)}")
        self._reserved[sku] += qty
        self.history.append(("reserve", sku, qty))

    def release(self, sku: str, qty: int) -> None:
        """Cancel ``qty`` reserved units. Raises ``InsufficientStock`` if fewer are reserved."""
        self._check_qty(qty)
        self._require(sku)
        if qty > self._reserved[sku]:
            raise InsufficientStock(f"{sku}: cannot release {qty}, reserved {self._reserved[sku]}")
        self._reserved[sku] -= qty
        self.history.append(("release", sku, qty))

    def ship(self, sku: str, qty: int) -> None:
        """Ship ``qty`` reserved units: reduces both on-hand and reserved quantities."""
        self._check_qty(qty)
        self._require(sku)
        if qty > self._reserved[sku]:
            raise InsufficientStock(f"{sku}: cannot ship {qty}, reserved {self._reserved[sku]}")
        self._reserved[sku] -= qty
        self._on_hand[sku] -= qty
        self.history.append(("ship", sku, qty))

    def adjust_down(self, sku: str, qty: int) -> None:
        """Write off ``qty`` damaged units. Only unreserved (available) units can be written off."""
        self._check_qty(qty)
        self._require(sku)
        if qty > self.available(sku):
            raise InsufficientStock(f"{sku}: cannot write off {qty}, available {self.available(sku)}")
        self._on_hand[sku] -= qty
        self.history.append(("adjust_down", sku, qty))

    def skus(self) -> List[str]:
        """Return all known SKUs sorted alphabetically."""
        return sorted(self._on_hand)

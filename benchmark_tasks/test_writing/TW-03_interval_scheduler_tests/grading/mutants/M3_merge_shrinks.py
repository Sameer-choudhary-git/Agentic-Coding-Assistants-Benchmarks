"""Half-open interval helpers for scheduling (times are integer minutes)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True, order=True)
class Interval:
    """A half-open interval ``[start, end)``.

    ``start`` and ``end`` are ints with ``start < end``; otherwise ``ValueError`` is raised.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise ValueError("bounds must be integers")
        if self.start >= self.end:
            raise ValueError("start must be strictly less than end")

    @property
    def length(self) -> int:
        return self.end - self.start


def overlaps(a: Interval, b: Interval) -> bool:
    """True if ``a`` and ``b`` share at least one minute. Touching intervals do not overlap."""
    return a.start < b.end and b.start < a.end


def merge_intervals(intervals: Iterable[Interval]) -> List[Interval]:
    """Merge overlapping **and touching** intervals.

    The input may be unsorted and is not modified. The result is sorted by start and contains
    no two intervals that overlap or touch. An empty input returns an empty list.
    """
    ordered = sorted(intervals)
    merged: List[Interval] = []
    for current in ordered:
        if merged and current.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = Interval(last.start, current.end)
        else:
            merged.append(current)
    return merged


def free_slots(busy: Iterable[Interval], window: Interval, min_length: int = 1) -> List[Interval]:
    """Return the free intervals inside ``window`` that are not covered by ``busy``.

    * Busy intervals are merged first; parts outside ``window`` are ignored (clipped).
    * Only free slots with ``length >= min_length`` are returned, sorted by start.
    * ``min_length`` must be >= 1, otherwise ``ValueError``.
    """
    if min_length < 1:
        raise ValueError("min_length must be >= 1")
    slots: List[Interval] = []
    cursor = window.start
    for block in merge_intervals(busy):
        if block.end <= window.start or block.start >= window.end:
            continue
        start = max(block.start, window.start)
        if start - cursor >= min_length:
            slots.append(Interval(cursor, start))
        cursor = max(cursor, min(block.end, window.end))
    if window.end - cursor >= min_length:
        slots.append(Interval(cursor, window.end))
    return slots

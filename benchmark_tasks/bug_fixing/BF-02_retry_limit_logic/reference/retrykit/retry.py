"""Retry helper with exponential backoff."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Type, TypeVar

R = TypeVar("R")


@dataclass(frozen=True)
class Backoff:
    """Exponential backoff policy.

    ``delay(k)`` returns the delay in seconds before retry number ``k`` (k starts at 1):
    ``min(base * factor ** (k - 1), max_delay)``.
    """

    base: float = 0.5
    factor: float = 2.0
    max_delay: float = 30.0

    def delay(self, retry_number: int) -> float:
        return min(self.base * self.factor ** (retry_number - 1), self.max_delay)


def retry_call(
    func: Callable[[], R],
    max_attempts: int = 3,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    backoff: Backoff = Backoff(),
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> R:
    """Call ``func`` until it succeeds or ``max_attempts`` calls have been made.

    * ``func`` is called at most ``max_attempts`` times in total; ``max_attempts`` must be >= 1
      (otherwise ``ValueError``).
    * Only exceptions that are instances of ``retry_on`` are retried. Any other exception
      propagates immediately without further attempts.
    * Before retry number ``k`` the function sleeps for ``backoff.delay(k)`` seconds using the
      injected ``sleep`` callable. No sleep happens after the final attempt.
    * If ``on_retry`` is given it is called as ``on_retry(attempt, exc, delay)`` before each sleep,
      where ``attempt`` is the 1-based number of the attempt that just failed.
    * If every attempt fails, the exception raised by the last attempt is re-raised unchanged.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retry_on as exc:
            if attempt == max_attempts:
                raise
            delay = backoff.delay(attempt)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover

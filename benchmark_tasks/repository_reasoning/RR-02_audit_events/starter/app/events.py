"""A minimal synchronous event bus.

Payload schema for user lifecycle events (all events below):
    {"user_id": int, "name": str, ...optional extra keys}
``name`` is the user's current name (for ``user.deleted``: the name the user had when deleted).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List, Tuple

USER_CREATED = "user.created"
USER_RENAMED = "user.renamed"
USER_DELETED = "user.deleted"
USER_EVENTS = (USER_CREATED, USER_RENAMED, USER_DELETED)

Handler = Callable[[str, Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)
        self.errors: List[Tuple[str, BaseException]] = []

    def subscribe(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, payload: Dict[str, Any]) -> None:
        """Deliver ``payload`` to every handler. Handler exceptions are recorded, never raised."""
        for handler in list(self._handlers[event]):
            try:
                handler(event, payload)
            except Exception as exc:  # noqa: BLE001 - isolation is intentional
                self.errors.append((event, exc))

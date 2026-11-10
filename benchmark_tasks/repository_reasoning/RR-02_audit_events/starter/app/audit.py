"""Audit log that listens to user lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.events import USER_EVENTS, EventBus


@dataclass(frozen=True)
class AuditEntry:
    event: str
    user_id: int
    name: Optional[str]


class AuditLog:
    def __init__(self, include_names: bool = True) -> None:
        self.include_names = include_names
        self.entries: List[AuditEntry] = []

    def attach(self, bus: EventBus) -> None:
        for event in USER_EVENTS:
            bus.subscribe(event, self.handle)

    def handle(self, event: str, payload: Dict[str, Any]) -> None:
        name = payload["name"] if self.include_names else None
        self.entries.append(AuditEntry(event=event, user_id=payload["user_id"], name=name))

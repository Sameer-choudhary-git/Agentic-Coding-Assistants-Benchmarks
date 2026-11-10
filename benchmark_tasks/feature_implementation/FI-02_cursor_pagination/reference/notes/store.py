"""An in-memory note store."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class InvalidCursor(ValueError):
    """Raised when a pagination cursor cannot be decoded."""


@dataclass(frozen=True)
class Note:
    id: int
    title: str
    created_at: float


def _encode_cursor(note: Note) -> str:
    raw = json.dumps([note.created_at, note.id]).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> Tuple[float, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        created_at, note_id = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any decoding problem is an invalid cursor
        raise InvalidCursor("invalid cursor") from exc
    if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
        raise InvalidCursor("invalid cursor")
    if not isinstance(note_id, int) or isinstance(note_id, bool):
        raise InvalidCursor("invalid cursor")
    return float(created_at), note_id


class NoteStore:
    def __init__(self) -> None:
        self._notes: Dict[int, Note] = {}
        self._next_id = 1

    def add(self, title: str, created_at: float) -> Note:
        note = Note(id=self._next_id, title=title, created_at=created_at)
        self._notes[note.id] = note
        self._next_id += 1
        return note

    def get(self, note_id: int) -> Optional[Note]:
        return self._notes.get(note_id)

    def delete(self, note_id: int) -> bool:
        return self._notes.pop(note_id, None) is not None

    def list_all(self) -> List[Note]:
        """Return all notes ordered by (created_at, id) ascending."""
        return sorted(self._notes.values(), key=lambda n: (n.created_at, n.id))

    def list_page(self, limit: int, cursor: Optional[str] = None) -> Tuple[List[Note], Optional[str]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an int between 1 and 100")
        ordered = self.list_all()
        if cursor is not None:
            if not isinstance(cursor, str):
                raise InvalidCursor("invalid cursor")
            position = _decode_cursor(cursor)
            ordered = [n for n in ordered if (n.created_at, n.id) > position]
        page = ordered[:limit]
        next_cursor = _encode_cursor(page[-1]) if len(ordered) > limit else None
        return page, next_cursor

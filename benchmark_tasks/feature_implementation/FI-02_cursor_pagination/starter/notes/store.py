"""An in-memory note store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Note:
    id: int
    title: str
    created_at: float


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

"""In-memory user repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class User:
    id: int
    name: str


class UserRepository:
    def __init__(self) -> None:
        self._users: Dict[int, User] = {}
        self._next = 1

    def add(self, name: str) -> User:
        user = User(self._next, name)
        self._users[user.id] = user
        self._next += 1
        return user

    def get(self, user_id: int) -> Optional[User]:
        return self._users.get(user_id)

    def remove(self, user_id: int) -> None:
        if user_id not in self._users:
            raise KeyError(user_id)
        del self._users[user_id]

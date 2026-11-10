"""User service: performs user operations and publishes lifecycle events."""

from __future__ import annotations

from app.events import USER_CREATED, USER_DELETED, USER_RENAMED, EventBus
from app.repository import User, UserRepository


class UserService:
    def __init__(self, repo: UserRepository, bus: EventBus) -> None:
        self.repo = repo
        self.bus = bus

    def create(self, name: str) -> User:
        user = self.repo.add(name)
        self.bus.publish(USER_CREATED, {"user_id": user.id, "name": user.name})
        return user

    def rename(self, user_id: int, new_name: str) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise KeyError(user_id)
        old_name, user.name = user.name, new_name
        self.bus.publish(USER_RENAMED, {"user_id": user.id, "name": user.name, "old_name": old_name})
        return user

    def delete(self, user_id: int) -> None:
        user = self.repo.get(user_id)
        if user is None:
            raise KeyError(user_id)
        name = user.name
        self.repo.remove(user_id)
        self.bus.publish(USER_DELETED, {"user_id": user_id, "name": name})

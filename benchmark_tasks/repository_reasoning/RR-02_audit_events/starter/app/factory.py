"""Application wiring."""

from __future__ import annotations

from dataclasses import dataclass

from app.audit import AuditLog
from app.config import Settings, parse_settings
from app.events import EventBus
from app.repository import UserRepository
from app.users import UserService


@dataclass
class App:
    settings: Settings
    bus: EventBus
    users: UserService
    audit: AuditLog


def create_app(settings_text: str = "") -> App:
    settings = parse_settings(settings_text)
    bus = EventBus()
    audit = AuditLog(include_names=settings.audit_include_names)
    if settings.audit_enabled:
        audit.attach(bus)
    users = UserService(UserRepository(), bus)
    return App(settings=settings, bus=bus, users=users, audit=audit)

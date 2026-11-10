import pytest

from app.config import Settings, parse_bool, parse_settings
from app.events import EventBus
from app.factory import create_app


def test_defaults():
    assert parse_settings("") == Settings(True, True)
    assert parse_bool(" YES ") is True


def test_bus_isolates_handler_errors():
    bus = EventBus()
    calls = []

    def bad(event, payload):
        raise RuntimeError("boom")

    bus.subscribe("x", bad)
    bus.subscribe("x", lambda e, p: calls.append(p))
    bus.publish("x", {"v": 1})
    assert calls == [{"v": 1}]
    assert len(bus.errors) == 1


def test_rename_and_unknown_user():
    app = create_app()
    user = app.users.create("a")
    app.users.rename(user.id, "b")
    assert app.users.repo.get(user.id).name == "b"
    with pytest.raises(KeyError):
        app.users.rename(999, "x")
    with pytest.raises(KeyError):
        app.users.delete(999)


def test_settings_line_without_equals_rejected():
    with pytest.raises(ValueError):
        parse_settings("audit.enabled true")

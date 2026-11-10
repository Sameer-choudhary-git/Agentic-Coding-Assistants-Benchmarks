import pytest

from app.audit import AuditEntry
from app.events import USER_DELETED
from app.factory import create_app


def lifecycle(app):
    a = app.users.create("ana")
    b = app.users.create("bo")
    app.users.rename(a.id, "anna")
    app.users.delete(b.id)
    app.users.delete(a.id)
    return a, b


def test_all_lifecycle_events_audited():
    app = create_app("audit.enabled = true\n")
    a, b = lifecycle(app)
    assert app.audit.entries == [
        AuditEntry("user.created", a.id, "ana"),
        AuditEntry("user.created", b.id, "bo"),
        AuditEntry("user.renamed", a.id, "anna"),
        AuditEntry("user.deleted", b.id, "bo"),
        AuditEntry("user.deleted", a.id, "anna"),
    ]


def test_deleted_payload_follows_schema():
    app = create_app("")
    seen = []
    app.bus.subscribe(USER_DELETED, lambda event, payload: seen.append(dict(payload)))
    user = app.users.create("cy")
    app.users.delete(user.id)
    assert len(seen) == 1
    assert seen[0].get("user_id") == user.id
    assert seen[0].get("name") == "cy"


@pytest.mark.parametrize("value", ["false", "FALSE", " no ", "Off", "0"])
def test_audit_disabled_values(value):
    app = create_app(f"# settings\naudit.enabled = {value}\n")
    lifecycle(app)
    assert app.settings.audit_enabled is False
    assert app.audit.entries == []


@pytest.mark.parametrize("key", ["audit.enabled", "audit.include_names"])
@pytest.mark.parametrize("value", ["maybe", "", "2", "truthy"])
def test_invalid_boolean_rejected(key, value):
    with pytest.raises(ValueError):
        create_app(f"{key} = {value}")


def test_no_bus_errors():
    app = create_app("audit.include_names = no")
    lifecycle(app)
    assert app.bus.errors == []
    assert [e.name for e in app.audit.entries] == [None] * 5

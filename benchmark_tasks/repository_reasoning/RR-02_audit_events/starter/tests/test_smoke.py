from app.factory import create_app


def test_create_is_audited():
    app = create_app("")
    app.users.create("ana")
    assert len(app.audit.entries) == 1

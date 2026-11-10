import dataclasses

from signup import FIELD_ORDER, FieldError, ValidationResult


def test_field_order_unchanged():
    assert FIELD_ORDER == ("username", "email", "age", "password", "password_confirm")


def test_dataclasses_unchanged():
    assert [f.name for f in dataclasses.fields(FieldError)] == ["field", "code"]
    assert [f.name for f in dataclasses.fields(ValidationResult)] == ["ok", "errors", "cleaned"]
    assert ValidationResult(ok=True).errors == []

import pytest

from signup import FieldError, validate_registration

VALID = {
    "username": "  Alice_01 ",
    "email": " Alice.Smith+news@Example.co.uk ",
    "age": 30,
    "password": "s3cretpass",
    "password_confirm": "s3cretpass",
}


def with_(**changes):
    data = dict(VALID)
    for key, value in changes.items():
        if value is ...:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def codes(result, name):
    return [e.code for e in result.errors if e.field == name]


def test_valid_registration():
    result = validate_registration(dict(VALID))
    assert result.ok is True
    assert result.errors == []
    assert result.cleaned == {
        "username": "alice_01",
        "email": "alice.smith+news@example.co.uk",
        "age": 30,
        "password": "s3cretpass",
    }


@pytest.mark.parametrize("name", ["username", "email", "age", "password", "password_confirm"])
@pytest.mark.parametrize("value", [..., None, "   "])
def test_required_fields(name, value):
    result = validate_registration(with_(**{name: value}))
    assert result.ok is False
    assert result.cleaned == {}
    assert codes(result, name) == ["required"]


@pytest.mark.parametrize(
    "value,code",
    [(123, "invalid_type"), ("ab", "too_short"), ("a" * 21, "too_long"), ("bad-name", "invalid_chars"),
     ("1abc", "must_start_with_letter"), ("_abc", "must_start_with_letter"), ("ab cd", "invalid_chars")],
)
def test_username_rules(value, code):
    assert codes(validate_registration(with_(username=value)), "username") == [code]


@pytest.mark.parametrize(
    "value,code",
    [(["a@b.cd"], "invalid_type"), ("no-at-sign.com", "invalid_format"), ("a@b", "invalid_format"),
     ("a@b.c", "invalid_format"), ("a b@c.de", "invalid_format"), ("a@-ok.io", None), ("x@sub.domain.org", None)],
)
def test_email_rule(value, code):
    expected = [] if code is None else [code]
    assert codes(validate_registration(with_(email=value)), "email") == expected


@pytest.mark.parametrize(
    "value,code",
    [(True, "invalid_type"), ("30", "invalid_type"), (30.0, "invalid_type"), (12, "too_young"),
     (121, "out_of_range"), (13, None), (120, None)],
)
def test_age_rules(value, code):
    expected = [] if code is None else [code]
    assert codes(validate_registration(with_(age=value)), "age") == expected


@pytest.mark.parametrize(
    "value,code",
    [(12345678, "invalid_type"), ("a1b2c3", "too_short"), ("abcdefgh", "too_weak"), ("12345678", "too_weak")],
)
def test_password_rules(value, code):
    assert codes(validate_registration(with_(password=value, password_confirm=value)), "password") == [code]


def test_password_confirm():
    result = validate_registration(with_(password_confirm="s3cretpasS"))
    assert result.errors == [FieldError("password_confirm", "mismatch")]


def test_collects_all_errors_in_order():
    data = {"password_confirm": "x", "age": 5, "email": "bad", "username": "1x", "password": "short"}
    result = validate_registration(data)
    assert result.errors == [
        FieldError("username", "too_short"),
        FieldError("email", "invalid_format"),
        FieldError("age", "too_young"),
        FieldError("password", "too_short"),
        FieldError("password_confirm", "mismatch"),
    ]


def test_unknown_fields():
    result = validate_registration(with_(zeta=1, admin=True, age=200))
    assert result.errors == [
        FieldError("age", "out_of_range"),
        FieldError("admin", "unknown_field"),
        FieldError("zeta", "unknown_field"),
    ]
    assert result.ok is False

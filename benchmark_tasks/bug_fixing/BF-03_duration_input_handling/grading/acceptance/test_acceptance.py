import pytest

from durations import parse_duration


@pytest.mark.parametrize(
    "text,expected",
    [("90s", 90), ("1h30m", 5400), ("1d", 86400), ("2h0m15s", 7215), ("1d2h3m4s", 93784), ("0s", 0)],
)
def test_valid_inputs(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text,expected", [("1H", 3600), ("  2m ", 120), ("1D2H", 93600), ("\t5S\n", 5)])
def test_case_and_padding(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["90", "1h30", "007"])
def test_bare_number_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["5m5m", "1h1h", "1s2s"])
def test_repeated_unit_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["30m1h", "1s1m", "2h1d"])
def test_out_of_order_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["-5s", "+5s", "1.5h", "1h 30m", "3w", "h", "1x2s"])
def test_garbage_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize("value", [None, 5, 1.5, b"5s"])
def test_type_error(value):
    with pytest.raises(TypeError):
        parse_duration(value)

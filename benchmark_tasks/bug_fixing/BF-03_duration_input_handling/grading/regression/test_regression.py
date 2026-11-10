import pytest

from durations import format_duration


@pytest.mark.parametrize("seconds,text", [(0, "0s"), (59, "59s"), (3600, "1h"), (93784, "1d2h3m4s"), (86460, "1d1m")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_format_negative():
    with pytest.raises(ValueError):
        format_duration(-1)

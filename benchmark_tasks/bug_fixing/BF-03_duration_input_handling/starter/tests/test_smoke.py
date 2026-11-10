from durations import format_duration


def test_format():
    assert format_duration(3661) == "1h1m1s"

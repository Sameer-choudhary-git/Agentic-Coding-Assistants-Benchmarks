from retrykit import Backoff, retry_call


def test_returns_value_on_first_success():
    sleeps = []
    assert retry_call(lambda: "v", sleep=sleeps.append) == "v"
    assert sleeps == []


def test_eventual_success_returns_value():
    calls = []

    def func():
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionError()
        return 7

    assert retry_call(func, max_attempts=3, retry_on=(ConnectionError,), sleep=lambda _: None) == 7


def test_backoff_defaults():
    b = Backoff()
    assert (b.base, b.factor, b.max_delay) == (0.5, 2.0, 30.0)

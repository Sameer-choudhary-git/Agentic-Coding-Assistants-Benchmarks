import pytest

from retrykit import Backoff, retry_call


class Boom(Exception):
    pass


def failing(counter, exc_factory=lambda n: Boom(f"fail {n}")):
    def func():
        counter.append(1)
        raise exc_factory(len(counter))

    return func


def test_call_count_respects_max_attempts():
    calls = []
    with pytest.raises(Boom):
        retry_call(failing(calls), max_attempts=3, sleep=lambda _: None)
    assert len(calls) == 3


def test_non_retryable_exception_propagates():
    calls = []
    sleeps = []
    with pytest.raises(TypeError):
        retry_call(
            failing(calls, lambda n: TypeError("bad")),
            max_attempts=5,
            retry_on=(ConnectionError,),
            sleep=sleeps.append,
        )
    assert len(calls) == 1
    assert sleeps == []


def test_delays_are_capped():
    sleeps = []
    with pytest.raises(Boom):
        retry_call(
            failing([]),
            max_attempts=6,
            backoff=Backoff(base=1.0, factor=3.0, max_delay=10.0),
            sleep=sleeps.append,
        )
    assert sleeps == [1.0, 3.0, 9.0, 10.0, 10.0]


def test_no_sleep_after_last_attempt():
    sleeps = []
    with pytest.raises(Boom):
        retry_call(failing([]), max_attempts=1, sleep=sleeps.append)
    assert sleeps == []


def test_last_exception_reraised():
    raised = []

    def func():
        exc = Boom(f"attempt {len(raised) + 1}")
        raised.append(exc)
        raise exc

    with pytest.raises(Boom) as info:
        retry_call(func, max_attempts=4, sleep=lambda _: None)
    assert info.value is raised[-1]
    assert str(info.value) == "attempt 4"


def test_on_retry_callback():
    events = []
    calls = []

    def func():
        calls.append(1)
        if len(calls) < 3:
            raise Boom("x")
        return "ok"

    result = retry_call(
        func,
        max_attempts=5,
        backoff=Backoff(base=0.5, factor=2.0, max_delay=30.0),
        sleep=lambda _: None,
        on_retry=lambda attempt, exc, delay: events.append((attempt, type(exc), delay)),
    )
    assert result == "ok"
    assert events == [(1, Boom, 0.5), (2, Boom, 1.0)]


@pytest.mark.parametrize("value", [0, -1])
def test_invalid_max_attempts(value):
    with pytest.raises(ValueError):
        retry_call(lambda: 1, max_attempts=value, sleep=lambda _: None)

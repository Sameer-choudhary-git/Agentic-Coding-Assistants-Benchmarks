from retrykit import retry_call


def test_success_first_try():
    assert retry_call(lambda: 42, sleep=lambda _: None) == 42

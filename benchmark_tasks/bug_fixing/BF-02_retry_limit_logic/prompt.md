# Task BF-02: Fix retry-limit and backoff logic

The package `retrykit` provides `retry_call()` in `retrykit/retry.py`. Operations teams report that:

- an operation configured with `max_attempts=3` is sometimes executed four times,
- programming errors such as `TypeError` are retried even though they are not listed in `retry_on`,
- the configured maximum backoff delay is ignored, and
- when all attempts fail, the caller receives a generic `RuntimeError` instead of the real error.

The docstrings in `retrykit/retry.py` are the authoritative specification. Fix the implementation so
that `retry_call()` and `Backoff` behave exactly as documented.

Constraints:
- Keep the public API (`retry_call`, `Backoff`, their parameters and defaults) unchanged.
- Keep the injected `sleep` parameter; never call `time.sleep` directly when a `sleep` function is supplied.
- Do not add third-party dependencies. You may add tests under `tests/`.

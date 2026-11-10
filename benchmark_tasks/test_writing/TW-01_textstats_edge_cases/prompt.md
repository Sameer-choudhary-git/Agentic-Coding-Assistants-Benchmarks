# Task TW-01: Write edge-case tests for `textstats`

The module `textstats/stats.py` is believed to be correct. Its docstrings describe the intended behaviour.
Write a thorough **pytest** test suite for it in `tests/test_stats.py`.

Your suite will be judged on:
1. It must pass against the current, unmodified implementation.
2. It must exercise the module well (high line coverage).
3. It must detect realistic bugs: it is run against hidden, slightly faulty variants of the module and
   should fail on as many of them as possible. Focus on the edge cases described in the docstrings
   (empty input, punctuation and case handling, ties, invalid arguments, rounding).

Constraints:
- Do **not** modify anything under `textstats/` — only add test files under `tests/`.
- Use only `pytest` and the standard library. Tests must be deterministic and must not use the network.

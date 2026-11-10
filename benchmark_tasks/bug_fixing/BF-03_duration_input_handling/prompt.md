# Task BF-03: Fix input handling in the duration parser

`durations/parse.py` exposes `parse_duration(text)` which converts strings such as `"1h30m"` into a
number of seconds, and `format_duration(seconds)` which does the reverse.

Bug reports:
- `parse_duration("")` returns `0` instead of failing.
- `parse_duration("90")` returns `0` instead of failing, and `"5m5m"` is accepted.
- `parse_duration("1H")` and `parse_duration("  2m ")` are rejected although they are valid.

The docstring of `parse_duration()` is the authoritative specification. Fix `parse_duration()` so it
behaves exactly as documented. `format_duration()` is correct and must keep its behaviour.

Constraints: keep function names and signatures; no third-party dependencies; you may add tests under `tests/`.

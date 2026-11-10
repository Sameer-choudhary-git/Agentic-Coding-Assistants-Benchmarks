# Task TW-03: Write tests for the interval scheduling module

`scheduling/intervals.py` provides helpers for half-open time intervals `[start, end)` represented as
integer minutes: `Interval`, `merge_intervals`, `free_slots` and `overlaps`. It is believed to be correct;
its docstrings describe the intended behaviour precisely.

Write a thorough **pytest** suite under `tests/` (for example `tests/test_intervals.py`).

Your suite will be judged on:
1. Passing against the current, unmodified implementation.
2. Line coverage of `scheduling/intervals.py`.
3. Detecting realistic bugs: it is run against hidden, slightly faulty variants of the module and should
   fail on as many as possible. Pay particular attention to boundary semantics: touching vs overlapping
   intervals, empty input, unsorted input, clipping to the search window, and the minimum slot length.

Constraints: do **not** modify anything under `scheduling/`; use only `pytest` and the standard library; tests must be deterministic.

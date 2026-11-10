# Task TW-02: Write tests for the inventory ledger

`inventory/ledger.py` implements a `Ledger` class that tracks stock levels and reservations per SKU.
It is believed to be correct; its docstrings describe the intended behaviour.

Write a thorough **pytest** suite under `tests/` (for example `tests/test_ledger.py`).

Your suite will be judged on:
1. Passing against the current, unmodified implementation.
2. Line coverage of `inventory/ledger.py`.
3. Detecting realistic bugs: it is run against hidden, slightly faulty variants of the module and should
   fail on as many as possible. Think about invariants (available = on hand − reserved), boundary values
   (exactly zero, exactly the available amount), error types, and multi-step scenarios.

Constraints: do **not** modify anything under `inventory/`; use only `pytest` and the standard library; tests must be deterministic.

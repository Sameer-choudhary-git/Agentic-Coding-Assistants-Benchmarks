# Task SR-01: Remediate SQL injection in the user repository

`userdb/repo.py` contains data-access functions for a SQLite `users` table. A security review found
that they build SQL statements with string formatting and are vulnerable to SQL injection.

Fix all functions in `userdb/repo.py` so that:
1. Every user-supplied value is passed to `sqlite3` as a bound parameter (`?` placeholders). No user
   input may be interpolated into SQL text.
2. `search_users(conn, prefix, order_by="name")` matches names that **start with** `prefix`, and the
   characters `%` and `_` inside `prefix` are treated literally (escape them and use `LIKE ... ESCAPE`).
3. `order_by` accepts only `"name"` or `"created_at"`; any other value raises `ValueError`.
4. Return values and behaviour for legitimate input stay exactly the same.

Constraints: keep function names, parameters and return types; use only the standard library; you may add tests under `tests/`.

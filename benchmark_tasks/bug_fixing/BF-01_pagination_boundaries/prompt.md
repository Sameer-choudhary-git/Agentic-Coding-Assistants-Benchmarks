# Task BF-01: Fix pagination boundary errors

You are working in a small Python package called `pager`.

Users report that `pager.paginate.paginate()` returns the wrong items, sometimes reports an
extra (or missing) page, and claims there is a next page when the user is already on the last one.

The docstring of `paginate()` is the authoritative specification. Fix the implementation in
`pager/paginate.py` so that it behaves exactly as the docstring describes.

Constraints:
- Do not change the function signature, the `Page` dataclass fields, or the module layout.
- Do not add third-party dependencies.
- You may add or update tests under `tests/`.

You are done when `paginate()` matches its docstring for all inputs.

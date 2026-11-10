# Task FI-03: Implement structured registration validation

`signup/validation.py` defines `FieldError`, `ValidationResult`, `FIELD_ORDER` and a stub
`validate_registration(data: dict) -> ValidationResult`. Implement it.

## Output
- Return `ValidationResult(ok=..., errors=[...], cleaned={...})`.
- `errors` is a list of `FieldError(field, code)`. Collect **all** errors, at most **one** per field:
  for each field apply the rules below in the listed order and report only the first rule that fails.
- Order errors by `FIELD_ORDER`; then append one `FieldError(key, "unknown_field")` for every key of
  `data` that is not in `FIELD_ORDER`, sorted alphabetically.
- `ok` is `True` only when `errors` is empty. When `ok` is `True`, `cleaned` contains every field from
  `FIELD_ORDER` except `password_confirm`, with `username` and `email` stripped and lower-cased and
  all other values unchanged. When `ok` is `False`, `cleaned` is `{}`.

## Rules (per field, checked in this order)
A value is *missing* if the key is absent, the value is `None`, or it is a string that is empty after `strip()`.

| Field | Rules in order |
|---|---|
| `username` | missing → `required`; not a `str` → `invalid_type`; after strip: length < 3 → `too_short`; length > 20 → `too_long`; contains characters other than `a-z`, `A-Z`, `0-9`, `_` → `invalid_chars`; first character not a letter → `must_start_with_letter` |
| `email` | missing → `required`; not a `str` → `invalid_type`; after strip it must match `local@domain.tld` where local is one or more of `A-Za-z0-9._+-`, domain labels are `A-Za-z0-9-`, separated by dots, and the final label (TLD) is 2+ letters; otherwise `invalid_format` |
| `age` | missing → `required`; not an `int` (note: `bool` is **not** accepted) → `invalid_type`; < 13 → `too_young`; > 120 → `out_of_range` |
| `password` | missing → `required`; not a `str` → `invalid_type`; length < 8 → `too_short`; no letter or no digit → `too_weak` |
| `password_confirm` | missing → `required`; not equal to `password` → `mismatch` |

Constraints: do not change the dataclasses or `FIELD_ORDER`; no third-party dependencies; you may add tests under `tests/`.

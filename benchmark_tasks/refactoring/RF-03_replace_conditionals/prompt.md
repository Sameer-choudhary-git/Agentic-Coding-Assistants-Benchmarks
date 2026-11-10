# Task RF-03: Replace plan conditionals with an extensible plan registry

`billing/plans.py` implements subscription rules for four plans (`free`, `team`, `business`,
`enterprise`) with long `if/elif` chains in three public functions:

- `monthly_price(plan: str, seats: int, annual: bool = False) -> Decimal`
- `seat_limit(plan: str) -> int | None` (`None` means unlimited)
- `can_upgrade(current: str, target: str) -> bool`

Adding a plan currently means editing every function. Refactor `billing/plans.py` (keep everything in this module) so that:

1. There is a base class `Plan` with class attributes `name: str` and `rank: int`, and methods
   `monthly_price(self, seats: int, annual: bool) -> Decimal` and `seat_limit(self) -> int | None`.
2. Each existing plan is a `Plan` subclass. Plans are stored in a module-level registry populated with
   `register_plan(plan_cls_or_instance)`; `get_plan(name) -> Plan` returns the registered instance and raises
   `UnknownPlanError` (a subclass of `KeyError`, defined in the module) for unknown names.
3. The three public functions keep their signatures and results, delegate to `get_plan(...)`, and contain no
   comparisons against plan-name strings.
4. Registering a **new** `Plan` subclass with `register_plan()` must make it work with all three public
   functions without modifying them. `can_upgrade(a, b)` is `True` exactly when `b` has a higher `rank` than `a`.
5. No function or method in the module may contain more than 3 branch nodes (`if`/`elif`, conditional
   expressions, `match` cases).
6. Input validation is unchanged: `seats` must be an `int` ≥ 1 (else `ValueError`), and exceeding a plan's seat
   limit raises `ValueError` from `monthly_price`.

All results must stay identical for every plan, seat count and `annual` flag. Standard library only; you may add tests under `tests/`.

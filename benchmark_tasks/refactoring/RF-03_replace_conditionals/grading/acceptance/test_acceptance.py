import ast
import inspect
from decimal import Decimal

import pytest

import billing.plans as plans

GOLDEN_PRICES = {
    "business|1000|False": "ValueError",
    "business|1000|True": "ValueError",
    "business|100|False": "1500.00",
    "business|100|True": "1200.00",
    "business|101|False": "1512.00",
    "business|101|True": "1209.60",
    "business|1|False": "15.00",
    "business|1|True": "12.00",
    "business|250|False": "3300.00",
    "business|250|True": "2640.00",
    "business|3|False": "45.00",
    "business|3|True": "36.00",
    "business|500|False": "6300.00",
    "business|500|True": "5040.00",
    "business|501|False": "ValueError",
    "business|501|True": "ValueError",
    "business|50|False": "750.00",
    "business|50|True": "600.00",
    "enterprise|1000|False": "10500.00",
    "enterprise|1000|True": "7875.00",
    "enterprise|100|False": "2500.00",
    "enterprise|100|True": "1875.00",
    "enterprise|101|False": "2500.00",
    "enterprise|101|True": "1875.00",
    "enterprise|1|False": "2500.00",
    "enterprise|1|True": "1875.00",
    "enterprise|250|False": "3000.00",
    "enterprise|250|True": "2250.00",
    "enterprise|3|False": "2500.00",
    "enterprise|3|True": "1875.00",
    "enterprise|500|False": "5500.00",
    "enterprise|500|True": "4125.00",
    "enterprise|501|False": "5510.00",
    "enterprise|501|True": "4132.50",
    "enterprise|50|False": "2500.00",
    "enterprise|50|True": "1875.00",
    "free|1000|False": "ValueError",
    "free|1000|True": "ValueError",
    "free|100|False": "ValueError",
    "free|100|True": "ValueError",
    "free|101|False": "ValueError",
    "free|101|True": "ValueError",
    "free|1|False": "0.00",
    "free|1|True": "0.00",
    "free|250|False": "ValueError",
    "free|250|True": "ValueError",
    "free|3|False": "0.00",
    "free|3|True": "0.00",
    "free|500|False": "ValueError",
    "free|500|True": "ValueError",
    "free|501|False": "ValueError",
    "free|501|True": "ValueError",
    "free|50|False": "ValueError",
    "free|50|True": "ValueError",
    "team|1000|False": "ValueError",
    "team|1000|True": "ValueError",
    "team|100|False": "ValueError",
    "team|100|True": "ValueError",
    "team|101|False": "ValueError",
    "team|101|True": "ValueError",
    "team|1|False": "8.00",
    "team|1|True": "6.80",
    "team|250|False": "ValueError",
    "team|250|True": "ValueError",
    "team|3|False": "24.00",
    "team|3|True": "20.40",
    "team|500|False": "ValueError",
    "team|500|True": "ValueError",
    "team|501|False": "ValueError",
    "team|501|True": "ValueError",
    "team|50|False": "400.00",
    "team|50|True": "340.00"
}

LIMITS = {"free": 3, "team": 50, "business": 500, "enterprise": None}
RANKS = {"free": 0, "team": 1, "business": 2, "enterprise": 3}
BRANCH_NODES = (ast.If, ast.IfExp) + ((ast.match_case,) if hasattr(ast, "match_case") else ())


def need(name):
    obj = getattr(plans, name, None)
    assert obj is not None, f"billing.plans.{name} is not defined"
    return obj


def test_prices_unchanged():
    mismatches = []
    for key in sorted(GOLDEN_PRICES):
        plan, seats, annual = key.split("|")
        expected = GOLDEN_PRICES[key]
        try:
            actual = str(plans.monthly_price(plan, int(seats), annual == "True"))
        except ValueError:
            actual = "ValueError"
        if actual != expected:
            mismatches.append((key, expected, actual))
    assert mismatches == []


def test_seat_limits_unchanged():
    for name, limit in LIMITS.items():
        assert plans.seat_limit(name) == limit
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ValueError):
            plans.monthly_price("team", bad)


def test_upgrade_rules_unchanged():
    for a, ra in RANKS.items():
        for b, rb in RANKS.items():
            assert plans.can_upgrade(a, b) is (rb > ra)


def test_unknown_plan():
    error = need("UnknownPlanError")
    assert issubclass(error, KeyError)
    with pytest.raises(error):
        plans.seat_limit("gold")
    with pytest.raises(error):
        plans.monthly_price("gold", 1)
    with pytest.raises(error):
        plans.can_upgrade("free", "gold")
    with pytest.raises(error):
        need("get_plan")("gold")


def test_new_plan_extensible():
    Plan = need("Plan")
    register_plan = need("register_plan")
    get_plan = need("get_plan")

    class StartupPlan(Plan):
        name = "startup_test_only"
        rank = 1

        def monthly_price(self, seats, annual):
            price = Decimal("5") * seats
            return price * Decimal("0.5") if annual else price

        def seat_limit(self):
            return 10

    register_plan(StartupPlan)
    assert isinstance(get_plan("startup_test_only"), StartupPlan)
    assert plans.monthly_price("startup_test_only", 4) == Decimal("20.00")
    assert plans.monthly_price("startup_test_only", 3, annual=True) == Decimal("7.50")
    assert plans.seat_limit("startup_test_only") == 10
    with pytest.raises(ValueError):
        plans.monthly_price("startup_test_only", 11)
    assert plans.can_upgrade("free", "startup_test_only") is True
    assert plans.can_upgrade("startup_test_only", "business") is True
    assert plans.can_upgrade("startup_test_only", "team") is False
    assert get_plan("team").rank == 1 and get_plan("enterprise").rank == 3


def test_low_branching():
    tree = ast.parse(inspect.getsource(plans))
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    plan_names = set(RANKS)
    for func in funcs:
        branches = sum(isinstance(n, BRANCH_NODES) for n in ast.walk(func))
        assert branches <= 3, f"{func.name} has {branches} branch nodes"
        if func.name in {"monthly_price", "seat_limit", "can_upgrade"}:
            for node in ast.walk(func):
                if isinstance(node, ast.Compare):
                    consts = {c.value for c in ast.walk(node) if isinstance(c, ast.Constant)}
                    assert not (consts & plan_names), f"{func.name} compares against plan names"

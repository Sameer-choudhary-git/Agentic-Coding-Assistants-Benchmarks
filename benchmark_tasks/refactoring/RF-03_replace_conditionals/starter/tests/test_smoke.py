from decimal import Decimal

from billing import monthly_price


def test_team_price():
    assert monthly_price("team", 2) == Decimal("16.00")

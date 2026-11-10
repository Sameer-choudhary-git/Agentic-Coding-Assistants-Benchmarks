from decimal import Decimal

from billing import can_upgrade, monthly_price, seat_limit


def test_public_api_basics():
    assert monthly_price("team", 10) == Decimal("80.00")
    assert monthly_price("team", 10, annual=True) == Decimal("68.00")
    assert seat_limit("enterprise") is None
    assert can_upgrade("team", "business") is True

import pytest

from inventory.ledger import InsufficientStock, InventoryError, Ledger, UnknownSku


@pytest.fixture()
def ledger():
    led = Ledger()
    led.receive("A", 10)
    return led


def test_receive_accumulates_and_creates(ledger):
    ledger.receive("A", 5)
    ledger.receive("B", 1)
    assert ledger.on_hand("A") == 15
    assert ledger.reserved("B") == 0
    assert ledger.skus() == ["A", "B"]


def test_skus_sorted():
    led = Ledger()
    for sku in ["zeta", "alpha", "mid"]:
        led.receive(sku, 1)
    assert led.skus() == ["alpha", "mid", "zeta"]


@pytest.mark.parametrize("qty", [0, -1, True, 1.5, "2"])
def test_invalid_quantities(ledger, qty):
    for op in (ledger.receive, ledger.reserve, ledger.release, ledger.ship, ledger.adjust_down):
        with pytest.raises(ValueError):
            op("A", qty)


def test_unknown_sku_errors():
    led = Ledger()
    assert issubclass(UnknownSku, KeyError) and issubclass(UnknownSku, InventoryError)
    for call in (led.on_hand, led.reserved, led.available):
        with pytest.raises(UnknownSku):
            call("nope")
    for op in (led.reserve, led.release, led.ship, led.adjust_down):
        with pytest.raises(UnknownSku):
            op("nope", 1)
    assert led.skus() == []


def test_reserve_up_to_available(ledger):
    ledger.reserve("A", 10)
    assert ledger.available("A") == 0
    assert ledger.reserved("A") == 10
    with pytest.raises(InsufficientStock):
        ledger.reserve("A", 1)


def test_reserve_too_much(ledger):
    with pytest.raises(InsufficientStock):
        ledger.reserve("A", 11)
    assert ledger.reserved("A") == 0


def test_release(ledger):
    ledger.reserve("A", 4)
    ledger.release("A", 4)
    assert ledger.available("A") == 10
    with pytest.raises(InsufficientStock):
        ledger.release("A", 1)


def test_ship_reduces_both(ledger):
    ledger.reserve("A", 6)
    ledger.ship("A", 4)
    assert (ledger.on_hand("A"), ledger.reserved("A"), ledger.available("A")) == (6, 2, 4)
    with pytest.raises(InsufficientStock):
        ledger.ship("A", 3)


def test_adjust_down_only_available(ledger):
    ledger.reserve("A", 7)
    ledger.adjust_down("A", 3)
    assert ledger.on_hand("A") == 7
    assert ledger.available("A") == 0
    with pytest.raises(InsufficientStock):
        ledger.adjust_down("A", 1)


def test_history_records_successful_operations(ledger):
    ledger.reserve("A", 2)
    ledger.release("A", 1)
    ledger.ship("A", 1)
    ledger.adjust_down("A", 1)
    with pytest.raises(InsufficientStock):
        ledger.ship("A", 5)
    assert ledger.history == [
        ("receive", "A", 10),
        ("reserve", "A", 2),
        ("release", "A", 1),
        ("ship", "A", 1),
        ("adjust_down", "A", 1),
    ]

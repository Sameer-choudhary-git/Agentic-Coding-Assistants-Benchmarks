import pytest

from scheduling.intervals import Interval, free_slots, merge_intervals, overlaps

I = Interval


@pytest.mark.parametrize("bounds", [(5, 5), (6, 5), (1.0, 2), (1, "2")])
def test_interval_validation(bounds):
    with pytest.raises(ValueError):
        I(*bounds)


def test_length():
    assert I(3, 10).length == 7


@pytest.mark.parametrize(
    "a,b,expected",
    [((0, 10), (5, 15), True), ((0, 10), (10, 20), False), ((10, 20), (0, 10), False),
     ((0, 10), (2, 3), True), ((0, 1), (1, 2), False), ((0, 10), (9, 11), True)],
)
def test_overlaps(a, b, expected):
    assert overlaps(I(*a), I(*b)) is expected


def test_merge_empty():
    assert merge_intervals([]) == []


def test_merge_touching_and_overlapping_unsorted():
    data = [I(10, 20), I(0, 5), I(5, 8), I(15, 25), I(30, 31)]
    original = list(data)
    assert merge_intervals(data) == [I(0, 8), I(10, 25), I(30, 31)]
    assert data == original


def test_merge_contained_interval():
    assert merge_intervals([I(0, 100), I(10, 20)]) == [I(0, 100)]


def test_free_slots_basic():
    window = I(0, 100)
    busy = [I(10, 20), I(15, 30), I(50, 60)]
    assert free_slots(busy, window) == [I(0, 10), I(30, 50), I(60, 100)]


def test_free_slots_no_busy():
    assert free_slots([], I(5, 9)) == [I(5, 9)]


def test_free_slots_clipping():
    window = I(100, 200)
    busy = [I(0, 100), I(90, 110), I(190, 300), I(250, 260)]
    assert free_slots(busy, window) == [I(110, 190)]
    assert free_slots([I(0, 100)], window) == [I(100, 200)]
    assert free_slots([I(150, 400)], window) == [I(100, 150)]


def test_free_slots_min_length_boundaries():
    window = I(0, 30)
    busy = [I(5, 10), I(15, 25)]
    assert free_slots(busy, window, min_length=5) == [I(0, 5), I(10, 15), I(25, 30)]
    assert free_slots(busy, window, min_length=6) == []


@pytest.mark.parametrize("value", [0, -5])
def test_free_slots_invalid_min_length(value):
    with pytest.raises(ValueError):
        free_slots([], I(0, 10), min_length=value)


def test_fully_busy_window():
    assert free_slots([I(0, 50), I(50, 100)], I(10, 90)) == []

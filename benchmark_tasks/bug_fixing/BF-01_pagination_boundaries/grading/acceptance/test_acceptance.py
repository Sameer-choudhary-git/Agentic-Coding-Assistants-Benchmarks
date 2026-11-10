import pytest

from pager import paginate

ITEMS = list(range(1, 24))  # 23 items


def test_first_page_slice():
    assert paginate(ITEMS, 1, 5).items == [1, 2, 3, 4, 5]
    assert paginate(ITEMS, 2, 5).items == [6, 7, 8, 9, 10]


def test_partial_last_page():
    page = paginate(ITEMS, 5, 5)
    assert page.items == [21, 22, 23]


def test_total_pages_rounds_up():
    assert paginate(ITEMS, 1, 5).total_pages == 5
    assert paginate(ITEMS, 1, 23).total_pages == 1
    assert paginate(ITEMS, 1, 100).total_pages == 1


def test_has_next_on_last_page():
    assert paginate(ITEMS, 4, 5).has_next is True
    assert paginate(ITEMS, 5, 5).has_next is False


def test_has_prev_flags():
    assert paginate(ITEMS, 1, 5).has_prev is False
    assert paginate(ITEMS, 2, 5).has_prev is True


def test_empty_list_page_one():
    page = paginate([], 1, 10)
    assert page.items == []
    assert page.total_pages == 0
    assert page.has_next is False
    assert page.has_prev is False


@pytest.mark.parametrize("page", [0, -1, 6, 7])
def test_out_of_range_page(page):
    with pytest.raises(ValueError):
        paginate(ITEMS, page, 5)


def test_exact_multiple():
    items = list(range(20))
    assert paginate(items, 1, 5).total_pages == 4
    assert paginate(items, 4, 5).items == [15, 16, 17, 18, 19]
    with pytest.raises(ValueError):
        paginate(items, 5, 5)
    with pytest.raises(ValueError):
        paginate([], 2, 5)

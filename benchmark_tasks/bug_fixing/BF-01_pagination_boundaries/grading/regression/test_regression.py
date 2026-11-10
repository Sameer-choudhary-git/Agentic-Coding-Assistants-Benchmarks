import pytest

from pager import Page, paginate


def test_returns_page_dataclass():
    result = paginate(["a", "b"], 1, 10)
    assert isinstance(result, Page)
    assert result.per_page == 10
    assert result.total_items == 2


@pytest.mark.parametrize("per_page", [0, -3])
def test_rejects_non_positive_per_page(per_page):
    with pytest.raises(ValueError):
        paginate([1, 2, 3], 1, per_page)


def test_accepts_tuples_and_returns_list():
    result = paginate((1, 2, 3), 1, 10)
    assert isinstance(result.items, list)

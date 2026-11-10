from pager import paginate


def test_returns_page_object():
    result = paginate([1, 2, 3], page=1, per_page=10)
    assert result.page == 1

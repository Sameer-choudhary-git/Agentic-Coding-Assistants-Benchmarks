import pytest

from library import api, storage
from library.models import Library
from library.validation import ValidationError


def test_existing_fields_and_filters(tmp_path):
    lib = Library()
    api.create_book(lib, title=" Dune ", author="Frank Herbert", year=1965)
    api.create_book(lib, title="Emma", author="Jane Austen", year=1815)
    assert [b.title for b in api.list_books(lib, year=1815)] == ["Emma"]
    assert lib.books[1].title == "Dune"
    with pytest.raises(ValidationError):
        api.create_book(lib, title="", author="x")
    with pytest.raises(ValidationError):
        api.create_book(lib, title="x", author="y", year=1200)
    with pytest.raises(ValidationError):
        api.update_book(lib, 99, title="x")
    path = tmp_path / "l.json"
    storage.save(lib, path)
    assert storage.load(path) == lib

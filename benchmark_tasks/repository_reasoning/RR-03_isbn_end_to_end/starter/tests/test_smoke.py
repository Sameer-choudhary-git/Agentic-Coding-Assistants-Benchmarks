from library.api import create_book, list_books
from library.models import Library


def test_create_and_list():
    lib = Library()
    create_book(lib, title="Dune", author="Frank Herbert", year=1965)
    assert [b.title for b in list_books(lib)] == ["Dune"]

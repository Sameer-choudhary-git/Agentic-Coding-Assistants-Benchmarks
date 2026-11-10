import json
import shutil
from pathlib import Path

import pytest

from library import api, storage
from library.models import Book, Library
from library.serializers import book_from_dict, book_to_dict
from library.validation import ValidationError

FIXTURES = Path(__file__).parent / "fixtures"
DUNE = "978-0-441-17271-9"      # valid ISBN-13
NEURO = "9780441569595"         # valid ISBN-13
LEFT = "978 0 441 47812 5"      # valid ISBN-13 with spaces


def test_create_with_isbn_normalised():
    lib = Library()
    book = api.create_book(lib, title="Dune", author="Frank Herbert", year=1965, isbn=DUNE)
    assert book.isbn == "9780441172719"
    plain = api.create_book(lib, title="No ISBN", author="Anon")
    assert plain.isbn is None
    assert Book(1, "t", "a").isbn is None


@pytest.mark.parametrize(
    "bad", ["9780441172718", "978044117271", "97804411727190", "978-0-441-1727X-9", "abcdefghijklm", 9780441172719]
)
def test_invalid_isbn_rejected(bad):
    lib = Library()
    with pytest.raises(ValidationError):
        api.create_book(lib, title="Dune", author="Frank Herbert", isbn=bad)
    assert lib.books == {}


def test_duplicate_isbn_rejected():
    lib = Library()
    first = api.create_book(lib, title="Dune", author="Frank Herbert", isbn=DUNE)
    with pytest.raises(ValidationError):
        api.create_book(lib, title="Dune (copy)", author="Frank Herbert", isbn="9780441172719")
    other = api.create_book(lib, title="Neuromancer", author="William Gibson", isbn=NEURO)
    with pytest.raises(ValidationError):
        api.update_book(lib, other.id, isbn=DUNE)
    assert api.update_book(lib, first.id, isbn=DUNE).isbn == "9780441172719"


def test_update_isbn():
    lib = Library()
    book = api.create_book(lib, title="The Left Hand of Darkness", author="Ursula K. Le Guin")
    api.update_book(lib, book.id, isbn=LEFT)
    assert book.isbn == "9780441478125"
    api.update_book(lib, book.id, title="LHoD")
    assert book.isbn == "9780441478125"
    api.update_book(lib, book.id, isbn=None)
    assert book.isbn is None
    with pytest.raises(ValidationError):
        api.update_book(lib, book.id, isbn="123")


def test_roundtrip_storage_v2(tmp_path):
    lib = Library()
    api.create_book(lib, title="Dune", author="Frank Herbert", year=1965, isbn=DUNE)
    api.create_book(lib, title="Untitled", author="Anon")
    path = tmp_path / "lib.json"
    storage.save(lib, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == 2
    assert [b["isbn"] for b in document["books"]] == ["9780441172719", None]
    loaded = storage.load(path)
    assert loaded == lib
    assert book_from_dict(book_to_dict(loaded.books[1])) == loaded.books[1]


def test_load_v1_file(tmp_path):
    path = tmp_path / "old.json"
    shutil.copy(FIXTURES / "library_v1.json", path)
    lib = storage.load(path)
    assert [b.isbn for b in lib.books.values()] == [None, None]
    assert lib.next_id == 3
    api.update_book(lib, 2, isbn=NEURO)
    storage.save(lib, path)
    again = storage.load(path)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2
    assert again.books[2].isbn == NEURO
    bad = tmp_path / "future.json"
    bad.write_text(json.dumps({"schema_version": 99, "books": [], "next_id": 1}), encoding="utf-8")
    with pytest.raises(storage.StorageError):
        storage.load(bad)


def test_list_books_isbn_filter():
    lib = Library()
    api.create_book(lib, title="Dune", author="Frank Herbert", isbn=DUNE)
    api.create_book(lib, title="Neuromancer", author="William Gibson", isbn=NEURO)
    api.create_book(lib, title="Untitled", author="Frank Herbert")
    assert [b.title for b in api.list_books(lib, isbn="9780441172719")] == ["Dune"]
    assert [b.title for b in api.list_books(lib, isbn="978 0441 56959-5")] == ["Neuromancer"]
    assert [b.title for b in api.list_books(lib, author="frank herbert", isbn=DUNE)] == ["Dune"]
    assert len(api.list_books(lib, author="Frank Herbert")) == 2

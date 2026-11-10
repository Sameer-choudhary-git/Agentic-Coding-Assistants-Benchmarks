"""Public operations on a library."""

from __future__ import annotations

from typing import List, Optional

from library.models import Book, Library
from library.validation import ValidationError, normalize_isbn, require_text, validate_year

_UNSET = object()


def _ensure_unique_isbn(library: Library, isbn: Optional[str], book_id: Optional[int]) -> None:
    if isbn is None:
        return
    for other in library.books.values():
        if other.isbn == isbn and other.id != book_id:
            raise ValidationError(f"isbn {isbn} is already used by book {other.id}")


def create_book(
    library: Library, *, title: str, author: str, year: Optional[int] = None, isbn: Optional[str] = None
) -> Book:
    normalized = normalize_isbn(isbn)
    _ensure_unique_isbn(library, normalized, None)
    book = Book(
        id=library.next_id,
        title=require_text(title, "title"),
        author=require_text(author, "author"),
        year=validate_year(year),
        isbn=normalized,
    )
    library.books[book.id] = book
    library.next_id += 1
    return book


def update_book(
    library: Library, book_id: int, *, title=_UNSET, author=_UNSET, year=_UNSET, isbn=_UNSET
) -> Book:
    book = library.books.get(book_id)
    if book is None:
        raise ValidationError(f"unknown book id {book_id}")
    if title is not _UNSET:
        book.title = require_text(title, "title")
    if author is not _UNSET:
        book.author = require_text(author, "author")
    if year is not _UNSET:
        book.year = validate_year(year)
    if isbn is not _UNSET:
        normalized = normalize_isbn(isbn)
        _ensure_unique_isbn(library, normalized, book.id)
        book.isbn = normalized
    return book


def list_books(
    library: Library,
    *,
    author: Optional[str] = None,
    year: Optional[int] = None,
    isbn: Optional[str] = None,
) -> List[Book]:
    books = [library.books[i] for i in sorted(library.books)]
    if author is not None:
        books = [b for b in books if b.author.casefold() == author.casefold()]
    if year is not None:
        books = [b for b in books if b.year == year]
    if isbn is not None:
        wanted = normalize_isbn(isbn)
        books = [b for b in books if b.isbn == wanted]
    return books

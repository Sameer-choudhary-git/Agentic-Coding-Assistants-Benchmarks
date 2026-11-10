"""Conversion between models and plain dicts."""

from __future__ import annotations

from typing import Any, Dict

from library.models import Book, Library


def book_to_dict(book: Book) -> Dict[str, Any]:
    return {"id": book.id, "title": book.title, "author": book.author, "year": book.year}


def book_from_dict(data: Dict[str, Any]) -> Book:
    return Book(id=data["id"], title=data["title"], author=data["author"], year=data.get("year"))


def library_to_dict(library: Library) -> Dict[str, Any]:
    return {
        "next_id": library.next_id,
        "books": [book_to_dict(library.books[i]) for i in sorted(library.books)],
    }


def library_from_dict(data: Dict[str, Any]) -> Library:
    books = {item["id"]: book_from_dict(item) for item in data["books"]}
    return Library(books=books, next_id=data["next_id"])

import re

import pytest

import notes
import notes.store as store_module
from notes import NoteStore


def invalid_cursor_cls():
    cls = getattr(store_module, "InvalidCursor", None)
    assert cls is not None, "notes.store.InvalidCursor is not defined"
    return cls


def make_store(n=7):
    store = NoteStore()
    for i in range(n):
        store.add(f"n{i}", created_at=float(10 + i))
    return store


def walk(store, limit):
    seen, cursor = [], None
    for _ in range(1000):
        page, cursor = store.list_page(limit, cursor)
        seen.extend(note.id for note in page)
        if cursor is None:
            return seen
    raise AssertionError("pagination did not terminate")


@pytest.mark.parametrize("limit", [1, 2, 3, 7, 100])
def test_pages_cover_all_notes_in_order(limit):
    store = make_store()
    assert walk(store, limit) == [n.id for n in store.list_all()]


def test_next_cursor_none_at_end():
    store = make_store(4)
    page, cursor = store.list_page(4)
    assert len(page) == 4
    assert cursor is None
    page, cursor = store.list_page(3)
    assert cursor is not None
    page, cursor = store.list_page(3, cursor)
    assert [n.title for n in page] == ["n3"]
    assert cursor is None


def test_ties_on_created_at_broken_by_id():
    store = NoteStore()
    a = store.add("a", 5.0)
    b = store.add("b", 1.0)
    c = store.add("c", 5.0)
    d = store.add("d", 5.0)
    assert walk(store, 2) == [b.id, a.id, c.id, d.id]


def test_deletion_between_pages_does_not_skip():
    store = make_store(6)
    page, cursor = store.list_page(2)
    for note in page:
        store.delete(note.id)
    rest, cursor = store.list_page(2, cursor)
    assert [n.title for n in rest] == ["n2", "n3"]
    store.add("late", created_at=99.0)
    remaining = []
    while cursor is not None:
        chunk, cursor = store.list_page(2, cursor)
        remaining.extend(n.title for n in chunk)
    assert remaining == ["n4", "n5", "late"]


def test_cursor_is_opaque_string():
    store = make_store(5)
    _, cursor = store.list_page(2)
    assert isinstance(cursor, str)
    assert re.fullmatch(r"[A-Za-z0-9_\-=]+", cursor)


@pytest.mark.parametrize("limit", [0, 101, -1, 2.5, "3", True])
def test_invalid_limit(limit):
    with pytest.raises(ValueError):
        make_store().list_page(limit)


@pytest.mark.parametrize("cursor", ["not-a-cursor!!", "%%%", "YWJj", ""])
def test_invalid_cursor(cursor):
    InvalidCursor = invalid_cursor_cls()
    assert issubclass(InvalidCursor, ValueError)
    assert getattr(notes, "InvalidCursor", None) is InvalidCursor
    with pytest.raises(InvalidCursor):
        make_store().list_page(2, cursor)


def test_empty_store():
    assert NoteStore().list_page(10) == ([], None)

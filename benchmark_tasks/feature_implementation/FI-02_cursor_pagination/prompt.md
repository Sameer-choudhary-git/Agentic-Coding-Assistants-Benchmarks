# Task FI-02: Add cursor-based pagination to NoteStore

`notes/store.py` defines an in-memory `NoteStore` with `add()`, `get()`, `delete()` and `list_all()`.
Clients need to page through notes without missing or duplicating items when notes are deleted
between requests. Offset-based pagination is not acceptable.

Implement:

1. A new exception `InvalidCursor`, a subclass of `ValueError`, defined in `notes/store.py` and
   exported from the `notes` package.
2. A new method `NoteStore.list_page(self, limit: int, cursor: str | None = None) -> tuple[list[Note], str | None]`:
   - Notes are ordered by `(created_at, id)` ascending (the same order as `list_all()`).
   - It returns up to `limit` notes that come strictly after the position encoded in `cursor`
     (or from the beginning if `cursor` is `None`), and a `next_cursor`.
   - `next_cursor` is `None` when no notes remain after the returned page; otherwise it is an opaque,
     URL-safe string (characters `A-Z a-z 0-9 - _ =` only) that encodes the position of the last returned note.
   - Paging must remain correct if notes that were already returned are deleted, or new notes with
     later `created_at` values are added, between calls (keyset pagination, not offsets).
   - `limit` must be an `int` between 1 and 100 inclusive, otherwise raise `ValueError`.
   - A cursor that cannot be decoded raises `InvalidCursor`.

Constraints: do not change existing methods' behaviour; no third-party dependencies; you may add tests under `tests/`.

# Task RR-03: Add a validated ISBN field end to end

The `library` package manages books through several layers:
`library/models.py` (dataclasses), `library/validation.py` (validation helpers and `ValidationError`),
`library/serializers.py` (dict conversion), `library/storage.py` (versioned JSON files) and
`library/api.py` (the public operations). Read how an existing field such as `year` flows through these
layers and follow the same conventions.

Add an optional `isbn` to books:
1. `Book` gets a new field `isbn: Optional[str] = None`, stored as a normalised 13-digit string.
2. `api.create_book(...)` and `api.update_book(...)` accept an `isbn` keyword argument. Normalise it by removing
   hyphens and spaces. A value is valid only if it is exactly 13 digits and the ISBN-13 checksum holds
   (weights alternate 1 and 3 from the left; the weighted sum of all 13 digits is divisible by 10).
   Otherwise raise `ValidationError`. Passing `isbn=None` means no ISBN (and, for `update_book`, clears it);
   omitting `isbn` in `update_book` leaves it unchanged.
3. ISBNs are unique within a `Library`; creating or updating a book with an ISBN used by another book raises `ValidationError`.
4. Serializers include `"isbn"`. Storage must write `"schema_version": 2` and must still load existing
   version 1 files (which have no `isbn`; treat it as `None`). Unknown versions keep raising `StorageError`.
5. `api.list_books(...)` gets an `isbn` keyword filter that accepts any format accepted by `create_book`.

Keep existing behaviour and signatures (only add the new keyword arguments). Standard library only; you may add tests under `tests/`.

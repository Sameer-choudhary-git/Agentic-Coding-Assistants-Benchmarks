from notes import NoteStore


def test_add_and_get():
    store = NoteStore()
    note = store.add("hello", 1.0)
    assert store.get(note.id) == note

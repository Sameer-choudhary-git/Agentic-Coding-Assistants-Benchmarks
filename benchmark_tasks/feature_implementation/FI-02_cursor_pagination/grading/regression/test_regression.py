from notes import NoteStore


def test_list_all_order_and_delete():
    store = NoteStore()
    a = store.add("a", 2.0)
    b = store.add("b", 1.0)
    assert store.list_all() == [b, a]
    assert store.delete(a.id) is True
    assert store.delete(a.id) is False
    assert store.get(a.id) is None


def test_ids_increment():
    store = NoteStore()
    assert [store.add(str(i), 0.0).id for i in range(3)] == [1, 2, 3]

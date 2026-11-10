import sqlite3

from userdb import create_schema, find_user_by_name, insert_user, search_users, update_email


def make():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    insert_user(c, "carol", "c@example.com", "2024-01-03")
    insert_user(c, "carl", "carl@example.com", "2024-01-01")
    insert_user(c, "dave", "d@example.com", "2024-01-02")
    return c


def test_find_existing_user():
    c = make()
    assert find_user_by_name(c, "dave") == (3, "dave", "d@example.com", "2024-01-02")


def test_search_orders():
    c = make()
    assert [u[1] for u in search_users(c, "car")] == ["carl", "carol"]
    assert [u[1] for u in search_users(c, "car", order_by="created_at")] == ["carl", "carol"]
    assert [u[1] for u in search_users(c, "")] == ["carl", "carol", "dave"]


def test_update_email_returns_rowcount():
    c = make()
    assert update_email(c, 1, "new@example.com") == 1
    assert find_user_by_name(c, "carol")[2] == "new@example.com"

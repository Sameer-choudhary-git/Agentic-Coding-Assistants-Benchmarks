import sqlite3

from userdb import create_schema, find_user_by_name, insert_user


def test_roundtrip():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    insert_user(conn, "ana", "ana@example.com", "2024-01-01")
    assert find_user_by_name(conn, "ana")[1] == "ana"

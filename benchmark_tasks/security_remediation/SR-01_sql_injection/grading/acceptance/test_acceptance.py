import sqlite3

import pytest

from userdb import create_schema, find_user_by_name, insert_user, search_users, update_email


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    create_schema(c)
    insert_user(c, "alice", "alice@example.com", "2024-03-01")
    insert_user(c, "bob", "bob@example.com", "2024-01-15")
    insert_user(c, "a_b", "ab@example.com", "2024-02-01")
    insert_user(c, "axb", "axb@example.com", "2024-02-02")
    insert_user(c, "100%", "pct@example.com", "2024-02-03")
    insert_user(c, "1000", "k@example.com", "2024-02-04")
    yield c
    c.close()


def count(c):
    return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def test_find_by_name_injection_returns_nothing(conn):
    assert find_user_by_name(conn, "' OR '1'='1") is None
    assert find_user_by_name(conn, "alice' --") is None


def test_find_by_name_drop_table_payload(conn):
    try:
        find_user_by_name(conn, "x'; DROP TABLE users; --")
    except sqlite3.Error:
        pass
    assert count(conn) == 6
    assert find_user_by_name(conn, "it's") is None
    insert_user(conn, "it's", "q@example.com", "2024-05-05")
    assert find_user_by_name(conn, "it's")[1] == "it's"


def test_search_prefix_wildcards_literal(conn):
    assert [u[1] for u in search_users(conn, "a_")] == ["a_b"]
    assert [u[1] for u in search_users(conn, "100%")] == ["100%"]
    assert search_users(conn, "' OR 1=1 --") == []


@pytest.mark.parametrize("order_by", ["id; DROP TABLE users", "email", "name DESC", "1", ""])
def test_order_by_allow_list(conn, order_by):
    with pytest.raises(ValueError):
        search_users(conn, "a", order_by=order_by)
    assert count(conn) == 6


def test_update_email_injection(conn):
    alice = find_user_by_name(conn, "alice")
    update_email(conn, alice[0], "x@example.com', name='pwned")
    names = sorted(r[0] for r in conn.execute("SELECT name FROM users"))
    assert "pwned" not in names
    assert find_user_by_name(conn, "alice")[2] == "x@example.com', name='pwned"
    update_email(conn, alice[0], "y@example.com'; DELETE FROM users; --")
    assert count(conn) == 6

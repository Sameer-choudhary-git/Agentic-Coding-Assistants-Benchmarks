"""Data access helpers for the users table."""

from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

User = Tuple[int, str, str, str]  # (id, name, email, created_at)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, created_at TEXT NOT NULL)"
    )


def insert_user(conn: sqlite3.Connection, name: str, email: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)", (name, email, created_at)
    )
    return int(cur.lastrowid)


def find_user_by_name(conn: sqlite3.Connection, name: str) -> Optional[User]:
    query = f"SELECT id, name, email, created_at FROM users WHERE name = '{name}'"
    row = conn.execute(query).fetchone()
    return tuple(row) if row else None


def search_users(conn: sqlite3.Connection, prefix: str, order_by: str = "name") -> List[User]:
    query = (
        "SELECT id, name, email, created_at FROM users "
        f"WHERE name LIKE '{prefix}%' ORDER BY {order_by}, id"
    )
    return [tuple(r) for r in conn.execute(query).fetchall()]


def update_email(conn: sqlite3.Connection, user_id: int, email: str) -> int:
    cur = conn.execute(f"UPDATE users SET email = '{email}' WHERE id = {int(user_id)}")
    return cur.rowcount

"""Data access helpers for the users table."""

from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

User = Tuple[int, str, str, str]  # (id, name, email, created_at)

_ORDER_COLUMNS = {"name": "name", "created_at": "created_at"}


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
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE name = ?", (name,)
    ).fetchone()
    return tuple(row) if row else None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_users(conn: sqlite3.Connection, prefix: str, order_by: str = "name") -> List[User]:
    column = _ORDER_COLUMNS.get(order_by)
    if column is None:
        raise ValueError(f"unsupported order_by: {order_by!r}")
    sql = (
        "SELECT id, name, email, created_at FROM users "
        "WHERE name LIKE ? ESCAPE '\\' ORDER BY " + column + ", id"  # column comes from allow-list
    )
    return [tuple(r) for r in conn.execute(sql, (_escape_like(prefix) + "%",)).fetchall()]


def update_email(conn: sqlite3.Connection, user_id: int, email: str) -> int:
    cur = conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, int(user_id)))
    return cur.rowcount

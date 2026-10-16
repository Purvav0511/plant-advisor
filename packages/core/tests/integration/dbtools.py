"""Plain helpers for the database integration tests. `conftest.py` turns them into fixtures;
tests that need their own connections (e.g. the concurrent-claims test) import them directly.

This folder is on pytest's and pyright's search path (pyproject.toml), so `import dbtools` works.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from typing import Any, LiteralString

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

# The Supabase CLI's fixed local default (also in .env.example). Not a secret.
DEFAULT_TEST_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

# Tables whose key isn't called `id`.
KEY_COLUMN = {"profiles": "user_id"}

# Types of the `insert` and `scalar` fixtures.
Insert = Callable[..., Any]
Scalar = Callable[[LiteralString, tuple[Any, ...]], Any]


def database_url() -> str:
    return os.environ.get("DATABASE_URL_TEST") or DEFAULT_TEST_URL


def to_param(value: Any) -> Any:
    """Dicts and lists of objects go in as JSON; lists of strings or UUIDs as Postgres arrays."""
    if isinstance(value, dict):
        return Jsonb(value)
    if isinstance(value, list) and not all(isinstance(v, str | uuid.UUID) for v in value):
        return Jsonb(value)
    return value


def insert_row(conn: psycopg.Connection, table: str, **values: Any) -> Any:
    """Insert one row and return its key. Names are composed with sql.Identifier, never
    pasted into the SQL text."""
    query = sql.SQL("insert into {table} ({cols}) values ({marks}) returning {key}").format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(map(sql.Identifier, values)),
        marks=sql.SQL(", ").join(sql.Placeholder() * len(values)),
        key=sql.Identifier(KEY_COLUMN.get(table, "id")),
    )
    row = conn.execute(query, [to_param(v) for v in values.values()]).fetchone()
    assert row is not None
    return row[0]


def scalar_of(conn: psycopg.Connection, query: LiteralString, params: tuple[Any, ...]) -> Any:
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def set_user(conn: psycopg.Connection, user_id: uuid.UUID) -> None:
    """Act as a signed-in user for the rest of the transaction, as the API does."""
    claims = json.dumps({"sub": str(user_id), "role": "authenticated"})
    conn.execute("set local role authenticated")
    conn.execute("select set_config('request.jwt.claims', %s, true)", (claims,))


def set_server(conn: psycopg.Connection) -> None:
    """Act as server code (the worker or a scheduler): the owner role, no login token."""
    conn.execute("reset role")
    conn.execute("select set_config('request.jwt.claims', '', true)")

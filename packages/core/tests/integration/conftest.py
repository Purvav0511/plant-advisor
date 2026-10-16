"""Shared fixtures for the database integration tests (`uv run poe test-int`).

- `db`: a connection to local Supabase whose transaction is rolled back after the test, so
  tests never leave data behind.
- `insert(table, **values)`: insert one row and return its key.
- `scalar(query, params)`: run a query returning one row and give back its first column.
- `as_user(user_id)` / `as_server()`: switch the connection's identity the way the API and
  the worker connect (decision 0012), for testing what each caller may do.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import psycopg
import pytest
from dbtools import Insert, Scalar, database_url, insert_row, scalar_of, set_server, set_user


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url()) as conn:
        try:
            yield conn
        finally:
            conn.rollback()


@pytest.fixture
def insert(db: psycopg.Connection) -> Insert:
    return lambda table, **values: insert_row(db, table, **values)


@pytest.fixture
def scalar(db: psycopg.Connection) -> Scalar:
    return lambda query, params: scalar_of(db, query, params)


@pytest.fixture
def as_user(db: psycopg.Connection) -> Callable[[uuid.UUID], None]:
    return lambda user_id: set_user(db, user_id)


@pytest.fixture
def as_server(db: psycopg.Connection) -> Callable[[], None]:
    return lambda: set_server(db)

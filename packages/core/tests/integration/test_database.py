"""Integration tests against local Supabase (`uv run poe test-int`, PLAN 0.4).

They check the database the rest of the system relies on: the extensions from the first
migration work, and the migrations recorded in the database match the files in the repo.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration

# The Supabase CLI's fixed local default (also in .env.example). Not a secret.
DEFAULT_TEST_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
MIGRATIONS = Path(__file__).resolve().parents[4] / "supabase" / "migrations"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    url = os.environ.get("DATABASE_URL_TEST") or DEFAULT_TEST_URL
    with psycopg.connect(url, autocommit=True) as connection:
        yield connection


def test_migrations_in_database_match_the_repo(conn: psycopg.Connection) -> None:
    files = sorted(p.name.split("_", 1)[0] for p in MIGRATIONS.glob("*.sql"))
    rows = conn.execute("select version from supabase_migrations.schema_migrations").fetchall()
    assert sorted(str(r[0]) for r in rows) == files


def test_pgvector_computes_distances(conn: psycopg.Connection) -> None:
    row = conn.execute(
        "select '[1,2,3]'::extensions.vector <-> '[1,2,4]'::extensions.vector"
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(1.0)


def test_pgmq_round_trip(conn: psycopg.Connection) -> None:
    queue = f"test_{uuid.uuid4().hex[:12]}"
    conn.execute("select pgmq.create(%s)", (queue,))
    try:
        conn.execute("select pgmq.send(%s, %s::jsonb)", (queue, '{"request_id": "r-1"}'))
        msg = conn.execute("select msg_id, read_ct, message from pgmq.read(%s, 30, 1)", (queue,))
        msg_id, read_ct, body = msg.fetchone() or (None, None, None)
        assert body == {"request_id": "r-1"}
        assert read_ct == 1
        archived = conn.execute("select pgmq.archive(%s, %s::bigint)", (queue, msg_id)).fetchone()
        assert archived is not None
        assert archived[0] is True
        empty = conn.execute("select count(*) from pgmq.read(%s, 30, 1)", (queue,)).fetchone()
        assert empty is not None
        assert empty[0] == 0
    finally:
        conn.execute("select pgmq.drop_queue(%s)", (queue,))

"""Integration tests for the database's rights (PLAN 1.3.a, decision 0023).

Supabase grants every right on every table to `anon` and `authenticated` by default, and
row-level security doesn't apply to some of them (TRUNCATE). After the lockdown:
- `anon` (signed out) has no rights at all;
- `authenticated` (signed in) may only read; RLS policies decide which rows, and each API
  task adds the writes its endpoint needs;
- `service_role` (worker, MCP) may read and write rows, but not truncate or alter tables;
- tables and functions created by later migrations start closed in the same way.
"""

from __future__ import annotations

import psycopg
import pytest

pytestmark = pytest.mark.integration

# MAINTAIN (Postgres 17) allows VACUUM, REINDEX and LOCK TABLE, so it matters too.
TABLE_RIGHTS = [
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
    "MAINTAIN",
]
ALLOWED = {
    "anon": set(),
    "authenticated": {"SELECT"},
    "service_role": {"SELECT", "INSERT", "UPDATE", "DELETE"},
}


def public_tables(db: psycopg.Connection) -> list[str]:
    rows = db.execute(
        "select tablename from pg_tables where schemaname = 'public' order by tablename"
    ).fetchall()
    return [r[0] for r in rows]


def rights(db: psycopg.Connection, role: str, table: str) -> set[str]:
    held = set()
    for right in TABLE_RIGHTS:
        row = db.execute(
            "select has_table_privilege(%s, %s, %s)", (role, f"public.{table}", right)
        ).fetchone()
        if row and row[0]:
            held.add(right)
    return held


@pytest.mark.parametrize("role", sorted(ALLOWED))
def test_each_role_holds_only_its_rights_on_every_table(db: psycopg.Connection, role: str) -> None:
    tables = public_tables(db)
    assert tables, "no tables found"
    for table in tables:
        expected = set(ALLOWED[role])
        if role == "service_role" and table == "requests":
            # Lock 1 from PLAN 1.2: the worker updates requests only through
            # transition_request(), so it holds column-level UPDATE, not table-level.
            expected.discard("UPDATE")
        assert rights(db, role, table) == expected, (role, table)


def test_the_worker_cannot_write_lifecycle_columns_directly(db: psycopg.Connection) -> None:
    for column in ("status", "attempt", "claimed_by"):
        held = db.execute(
            "select has_column_privilege('service_role', 'public.requests', %s, 'UPDATE')",
            (column,),
        ).fetchone()
        assert held == (False,), column


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_no_column_can_be_written_by_signed_in_or_signed_out_users(
    db: psycopg.Connection, role: str
) -> None:
    # Column grants survive a table-level revoke unless removed too, so check every column.
    rows = db.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'public'"
    ).fetchall()
    for table, column in rows:
        for right in ("INSERT", "UPDATE", "REFERENCES"):
            held = db.execute(
                "select has_column_privilege(%s, %s, %s, %s)",
                (role, f"public.{table}", column, right),
            ).fetchone()
            assert held == (False,), (role, table, column, right)


def test_signed_out_visitors_cannot_run_any_of_our_functions(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select p.oid::regprocedure::text from pg_proc p "
        "join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public'"
    ).fetchall()
    assert rows
    for (signature,) in rows:
        held = db.execute("select has_function_privilege('anon', %s, 'EXECUTE')", (signature,))
        assert held.fetchone() == (False,), signature


def test_only_the_gatekeeper_can_be_called_by_signed_in_users(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select p.oid::regprocedure::text from pg_proc p "
        "join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'public' and has_function_privilege('authenticated', p.oid, 'EXECUTE')"
    ).fetchall()
    assert [r[0] for r in rows] == ["transition_request(uuid,text,text,text)"]


def test_a_table_added_later_starts_closed(db: psycopg.Connection) -> None:
    db.execute("create table public.added_later (id int primary key)")
    assert rights(db, "anon", "added_later") == set()
    assert rights(db, "authenticated", "added_later") == set()
    assert "TRUNCATE" not in rights(db, "service_role", "added_later")


def test_a_function_added_later_starts_closed(db: psycopg.Connection) -> None:
    db.execute("create function public.added_later() returns int language sql as 'select 1'")
    for role in ("anon", "authenticated"):
        held = db.execute(
            "select has_function_privilege(%s, 'public.added_later()', 'EXECUTE')", (role,)
        ).fetchone()
        assert held == (False,), role

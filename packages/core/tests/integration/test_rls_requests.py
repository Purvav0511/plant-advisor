"""Who sees which requests and the records attached to them (PLAN 1.3.e).

Plant users see every request at their plants (the shared history) with its photos,
messages, quotes, outcomes and timeline. The AI's raw output, reviews, case memory, the
ticket chat and knowledge proposals are staff-only: plant users get a filtered view of the
analysis through the API (PLAN 4.3, CLAUDE.md invariant 13).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from psycopg import sql

pytestmark = pytest.mark.integration

World = dict[str, dict[str, Any]]
STAFF = ["engineer", "sales", "admin", "staff_off_request"]
PLANT_USERS = {"plant_user": "p1", "plant_user_p2": "p2"}

# Tables a plant user sees for their plants' requests: (table, fixture key prefix).
SHARED = [
    ("requests", "request"),
    ("request_photos", "photo"),
    ("messages", "message"),
    ("quotes", "quote"),
    ("outcomes", "outcome"),
]
STAFF_ONLY = [
    ("pipeline_runs", "run"),
    ("analyses", "analysis"),
    ("reviews", "review"),
    ("cases", "case"),
    ("chat_messages", "chat"),
    ("knowledge_proposals", "proposal"),
]


def visible(
    db: psycopg.Connection, as_user: Callable[[uuid.UUID], None], user: Any, table: str
) -> set[Any]:
    as_user(user)
    query = sql.SQL("select id from {}").format(sql.Identifier(table))
    rows = {r[0] for r in db.execute(query).fetchall()}
    db.execute("reset role")
    return rows


@pytest.mark.parametrize(("table", "prefix"), SHARED + STAFF_ONLY)
@pytest.mark.parametrize("person", STAFF)
def test_staff_see_every_request_and_record(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    prefix: str,
    person: str,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], table) == {w[f"{prefix}_p1"], w[f"{prefix}_p2"]}


@pytest.mark.parametrize(("table", "prefix"), SHARED)
@pytest.mark.parametrize(("person", "plant"), PLANT_USERS.items())
def test_plant_users_see_their_plants_requests_and_records(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    prefix: str,
    person: str,
    plant: str,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], table) == {w[f"{prefix}_{plant}"]}


def test_a_colleagues_request_at_the_same_plant_is_shared_history(
    db: psycopg.Connection,
    suppliers: World,
    insert: Callable[..., Any],
    as_user: Callable[[uuid.UUID], None],
) -> None:
    w = suppliers["a"]
    # Another plant user at p1 files a request; the first plant user sees it too.
    colleague = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (colleague,))
    insert(
        "profiles",
        user_id=colleague,
        tenant_id=w["tenant"],
        roles=["plant_user"],
        plant_ids=[w["p1"]],
        customer_id=w["customer"],
    )
    theirs = insert(
        "requests",
        tenant_id=w["tenant"],
        customer_id=w["customer"],
        plant_id=w["p1"],
        component_id=w["component_p1"],
        playbook_id="wear_protection",
        created_by=colleague,
    )
    assert visible(db, as_user, w["plant_user"], "requests") == {w["request_p1"], theirs}


@pytest.mark.parametrize(("table", "prefix"), STAFF_ONLY)
@pytest.mark.parametrize("person", PLANT_USERS)
def test_plant_users_never_see_the_staff_only_records(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    prefix: str,
    person: str,
) -> None:
    for name in ("a", "b"):
        assert visible(db, as_user, suppliers[name][person], table) == set()


# --- the timeline ------------------------------------------------------------------------


def events_of(db: psycopg.Connection, request: Any, types: tuple[str, ...]) -> set[Any]:
    rows = db.execute(
        "select id from events where request_id = %s and type = any (%s)", (request, list(types))
    ).fetchall()
    return {r[0] for r in rows}


@pytest.mark.parametrize(("person", "plant"), PLANT_USERS.items())
def test_plant_users_see_their_requests_timeline_but_not_internal_events(
    db: psycopg.Connection,
    suppliers: World,
    insert: Callable[..., Any],
    as_user: Callable[[uuid.UUID], None],
    person: str,
    plant: str,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        request = w[f"request_{plant}"]
        insert(
            "events",
            tenant_id=w["tenant"],
            request_id=request,
            type="analysis_ready",
            payload={"confidence": 0.4},
        )
        timeline = events_of(db, request, ("request_created", "status_changed"))
        assert timeline, "the request should have a creation event"
        assert visible(db, as_user, w[person], "events") == timeline


@pytest.mark.parametrize("person", STAFF)
def test_staff_see_every_event_at_their_supplier(
    db: psycopg.Connection,
    suppliers: World,
    insert: Callable[..., Any],
    as_user: Callable[[uuid.UUID], None],
    person: str,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        insert("events", tenant_id=w["tenant"], type="nightly_report", payload={})
        rows = db.execute("select id from events where tenant_id = %s", (w["tenant"],))
        assert visible(db, as_user, w[person], "events") == {r[0] for r in rows.fetchall()}


# --- completeness --------------------------------------------------------------------------


def test_every_table_has_a_read_policy_for_signed_in_users(db: psycopg.Connection) -> None:
    # A new table without one would silently show nothing; this makes it a decision.
    rows = db.execute(
        "select t.tablename from pg_tables t where t.schemaname = 'public' and not exists ("
        "  select 1 from pg_policies p where p.schemaname = 'public' and p.tablename = t.tablename"
        "   and p.cmd in ('SELECT', 'ALL') and 'authenticated' = any (p.roles))"
    ).fetchall()
    assert rows == []

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
from typing import Any

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


# --- two suppliers, every role, one row in every table (PLAN 1.3) -----------------------


def add_person(
    db: psycopg.Connection,
    insert: Insert,
    w: dict[str, Any],
    key: str,
    roles: list[str],
    plants: list[Any],
    customer: Any = None,
) -> None:
    """Create a signed-in user with a profile in supplier `w`, stored as w[key]."""
    user = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (user,))
    insert(
        "profiles",
        user_id=user,
        tenant_id=w["tenant"],
        roles=roles,
        plant_ids=plants,
        customer_id=customer,
        display_name=key,
    )
    w[key] = user


def build_supplier(db: psycopg.Connection, insert: Insert, name: str) -> dict[str, Any]:
    """One supplier with two plants (p1, p2), its people, and rows in every table."""
    w: dict[str, Any] = {}
    t = w["tenant"] = insert("tenants", name=f"Supplier {name}")
    w["customer"] = insert("customers", tenant_id=t, name=f"Customer {name}")
    for p in ("p1", "p2"):
        w[p] = insert("plants", tenant_id=t, customer_id=w["customer"], name=f"{name}-{p}")
        w[f"component_{p}"] = insert(
            "components",
            tenant_id=t,
            plant_id=w[p],
            playbook_id="wear_protection",
            component_type="chute",
            name=f"{name}-{p}-chute",
        )

    add_person(db, insert, w, "plant_user", ["plant_user"], [w["p1"]], w["customer"])
    add_person(db, insert, w, "plant_user_p2", ["plant_user"], [w["p2"]], w["customer"])
    add_person(db, insert, w, "engineer", ["engineer"], [])
    add_person(db, insert, w, "sales", ["sales"], [])
    add_person(db, insert, w, "admin", ["admin"], [])
    add_person(db, insert, w, "staff_off_request", ["engineer"], [])

    w["invite"] = insert(
        "plant_invites",
        tenant_id=t,
        customer_id=w["customer"],
        code=f"INV-{uuid.uuid4().hex[:8]}",
        plant_ids=[w["p1"]],
        expires_at="2030-01-01T00:00:00Z",
        created_by=w["admin"],
    )

    # Knowledge in both states: plant users may see approved rows only (PLAN 1.3.d).
    for version, status in ((1, "approved"), (2, "draft")):
        db.execute(
            "insert into playbooks (id, tenant_id, version, status, config, family_schema) "
            "values ('wear_protection', %s, %s, %s, '{}', '{}')",
            (t, version, status),
        )
        w[f"vocab_{status}"] = insert(
            "vocab_terms",
            tenant_id=t,
            playbook_id="wear_protection",
            kind="mechanisms",
            code=f"abrasion-{status}",
            label="Abrasion",
            status=status,
        )
        w[f"product_{status}"] = insert(
            "products",
            tenant_id=t,
            code=f"wp-{name}-{status}",
            family="composite_wear_plate",
            name="Plate",
            status=status,
        )
        w[f"image_{status}"] = insert(
            "product_images",
            tenant_id=t,
            product_id=w[f"product_{status}"],
            r2_key="x.jpg",
            kind="catalog",
        )
    w["rule"] = insert(
        "rules",
        tenant_id=t,
        playbook_id="wear_protection",
        kind="remedy",
        name="r",
        condition={},
        action={},
        status="approved",
    )
    w["issue"] = insert(
        "ingestion_issues", tenant_id=t, source_doc="s.pdf", issue="x", severity="info"
    )

    # One request per plant, with a row in every request table. The p1 request has the
    # sales person as its contact and the engineer as a message author (PLAN 1.3.c).
    for p in ("p1", "p2"):
        w[f"installation_{p}"] = insert(
            "installations",
            tenant_id=t,
            component_id=w[f"component_{p}"],
            product_id=w["product_approved"],
        )
        r = w[f"request_{p}"] = insert(
            "requests",
            tenant_id=t,
            customer_id=w["customer"],
            plant_id=w[p],
            component_id=w[f"component_{p}"],
            playbook_id="wear_protection",
            created_by=w["plant_user"] if p == "p1" else w["plant_user_p2"],
            contact_user_id=w["sales"] if p == "p1" else None,
        )
        rows = {
            "photo": ("request_photos", {"r2_key": "p.jpg", "kind": "overview"}),
            "run": ("pipeline_runs", {"attempt": 1, "stage": "context", "status": "succeeded"}),
            "analysis": ("analyses", {"attempt": 1}),
            "review": ("reviews", {"engineer_id": w["engineer"], "decision": "approved"}),
            "message": ("messages", {"author_id": w["engineer"], "body": "hello"}),
            "quote": ("quotes", {"items": [{"code": "x"}]}),
            "outcome": ("outcomes", {"component_id": w[f"component_{p}"]}),
            "case": ("cases", {"playbook_id": "wear_protection"}),
            "chat": ("chat_messages", {"role": "assistant", "body": "hi"}),
            "proposal": (
                "knowledge_proposals",
                {"kind": "rule", "target": {}, "change": {}, "proposed_by": "chat"},
            ),
        }
        for key, (table, values) in rows.items():
            w[f"{key}_{p}"] = insert(table, tenant_id=t, request_id=r, **values)
    return w


@pytest.fixture
def suppliers(db: psycopg.Connection, insert: Insert) -> dict[str, dict[str, Any]]:
    """Two suppliers, "a" and "b", built by build_supplier(). Keys look like
    suppliers["a"]["request_p1"] or suppliers["b"]["engineer"]."""
    return {name: build_supplier(db, insert, name) for name in ("a", "b")}

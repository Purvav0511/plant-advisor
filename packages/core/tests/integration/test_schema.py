"""Integration tests for the core schema (PLAN 1.1, SPEC §5, decision 0022).

Each test runs in a transaction that is rolled back, so nothing is left behind.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any, LiteralString

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration

DEFAULT_TEST_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

# Every table SPEC §5 defines. A table added or dropped without updating this fails a test.
TABLES = {
    "tenants",
    "customers",
    "plants",
    "profiles",
    "plant_invites",
    "components",
    "installations",
    "playbooks",
    "vocab_terms",
    "products",
    "product_images",
    "rules",
    "ingestion_issues",
    "requests",
    "request_photos",
    "pipeline_runs",
    "analyses",
    "reviews",
    "messages",
    "quotes",
    "outcomes",
    "cases",
    "chat_messages",
    "knowledge_proposals",
    "events",
}

VECTOR_COLUMNS = {
    ("products", "text_embedding", 384),
    ("product_images", "image_embedding", 512),
    ("request_photos", "image_embedding", 512),
    ("cases", "image_embedding", 512),
    ("cases", "text_embedding", 384),
}


@pytest.fixture
def db() -> Iterator[psycopg.Connection]:
    url = os.environ.get("DATABASE_URL_TEST") or DEFAULT_TEST_URL
    with psycopg.connect(url) as conn:
        try:
            yield conn
        finally:
            conn.rollback()


# Tables whose key isn't called `id`.
KEY_COLUMN = {"profiles": "user_id"}


def to_param(value: Any) -> Any:
    """Dicts and lists of objects go in as JSON; lists of strings or UUIDs as Postgres arrays."""
    if isinstance(value, dict):
        return Jsonb(value)
    if isinstance(value, list) and not all(isinstance(v, str | uuid.UUID) for v in value):
        return Jsonb(value)
    return value


def insert(db: psycopg.Connection, table: str, **values: Any) -> Any:
    """Insert one row and return its key."""
    # Names are composed with sql.Identifier, never pasted into the SQL text.
    query = sql.SQL("insert into {table} ({cols}) values ({marks}) returning {key}").format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(map(sql.Identifier, values)),
        marks=sql.SQL(", ").join(sql.Placeholder() * len(values)),
        key=sql.Identifier(KEY_COLUMN.get(table, "id")),
    )
    row = db.execute(query, [to_param(v) for v in values.values()]).fetchone()
    assert row is not None
    return row[0]


def scalar(db: psycopg.Connection, query: LiteralString, params: tuple[Any, ...]) -> Any:
    """Run a query that returns one row and give back its first column."""
    row = db.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def vec(dim: int) -> str:
    return "[" + ",".join(["0.1"] * dim) + "]"


@pytest.fixture
def world(db: psycopg.Connection) -> dict[str, Any]:
    """One row in every table, inserted in dependency order. Returns their keys."""
    w: dict[str, Any] = {}
    w["tenant"] = insert(db, "tenants", name="Supplier A")
    t = w["tenant"]
    w["customer"] = insert(db, "customers", tenant_id=t, name="Cement Co")
    w["plant"] = insert(
        db, "plants", tenant_id=t, customer_id=w["customer"], name="Plant 1", location="North"
    )
    w["user"] = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (w["user"],))
    insert(
        db,
        "profiles",
        user_id=w["user"],
        tenant_id=t,
        roles=["engineer", "sales"],
        display_name="Eng One",
        phone="+10000000000",
    )
    w["invite"] = insert(
        db,
        "plant_invites",
        tenant_id=t,
        customer_id=w["customer"],
        code=f"INV-{uuid.uuid4().hex[:8]}",
        plant_ids=[w["plant"]],
        roles=["plant_user"],
        expires_at="2030-01-01T00:00:00Z",
        max_uses=5,
        created_by=w["user"],
    )
    w["component"] = insert(
        db,
        "components",
        tenant_id=t,
        plant_id=w["plant"],
        playbook_id="wear_protection",
        component_type="chute",
        name="Kiln feed chute",
    )
    w["playbook"] = scalar(
        db,
        "insert into playbooks (id, tenant_id, version, status, config, family_schema) "
        "values ('wear_protection', %s, 1, 'draft', %s, %s) returning id",
        (t, Jsonb({}), Jsonb({})),
    )
    w["vocab"] = insert(
        db,
        "vocab_terms",
        tenant_id=t,
        playbook_id="wear_protection",
        kind="mechanisms",
        code="abrasion",
        label="Abrasion",
        status="draft",
        version=1,
    )
    w["product"] = scalar(
        db,
        "insert into products (tenant_id, code, family, name, attributes, status, version, "
        "text_embedding) values (%s, 'wp-test', 'composite_wear_plate', 'Test plate', %s, "
        "'draft', 1, %s::extensions.vector) returning id",
        (t, Jsonb({"anti_sticking": False}), vec(384)),
    )
    w["product_image"] = scalar(
        db,
        "insert into product_images (tenant_id, product_id, r2_key, kind, image_embedding) "
        "values (%s, %s, 'catalog/x.jpg', 'catalog', %s::extensions.vector) returning id",
        (t, w["product"], vec(512)),
    )
    w["installation"] = insert(
        db,
        "installations",
        tenant_id=t,
        component_id=w["component"],
        product_id=w["product"],
        description="Mild steel liner",
        installed_on="2026-01-01",
    )
    w["rule"] = insert(
        db,
        "rules",
        tenant_id=t,
        playbook_id="wear_protection",
        kind="remedy",
        name="abrasion_rule",
        condition={">=": [1, 0]},
        action={"require": []},
        status="draft",
        version=1,
    )
    w["issue"] = insert(
        db,
        "ingestion_issues",
        tenant_id=t,
        source_doc="sheet.pdf",
        field="composition",
        issue="missing values",
        severity="warning",
    )
    w["request"] = insert(
        db,
        "requests",
        tenant_id=t,
        customer_id=w["customer"],
        plant_id=w["plant"],
        component_id=w["component"],
        playbook_id="wear_protection",
        created_by=w["user"],
        answers={"temperature": "ambient"},
    )
    r = w["request"]
    w["photo"] = scalar(
        db,
        "insert into request_photos (tenant_id, request_id, r2_key, kind, client_quality, "
        "image_embedding) values (%s, %s, 'req/a.jpg', 'overview', %s, %s::extensions.vector) "
        "returning id",
        (t, r, Jsonb({"blur": 0.9}), vec(512)),
    )
    w["run"] = insert(
        db,
        "pipeline_runs",
        tenant_id=t,
        request_id=r,
        attempt=1,
        stage="context",
        status="succeeded",
        input_hash="abc",
        output={},
    )
    w["analysis"] = insert(
        db,
        "analyses",
        request_id=r,
        attempt=1,
        tenant_id=t,
        confidence=0.72,
        flags=["low_confidence"],
        versions={"model": "m"},
    )
    w["review"] = insert(
        db, "reviews", tenant_id=t, request_id=r, engineer_id=w["user"], decision="approved"
    )
    w["message"] = insert(
        db,
        "messages",
        tenant_id=t,
        request_id=r,
        author_id=w["user"],
        body="Can you send a close-up?",
    )
    w["quote"] = insert(db, "quotes", tenant_id=t, request_id=r, items=[{"code": "wp-test"}])
    w["outcome"] = insert(
        db,
        "outcomes",
        tenant_id=t,
        request_id=r,
        component_id=w["component"],
        reported_life_days=120,
        resolved=True,
    )
    w["case"] = scalar(
        db,
        "insert into cases (tenant_id, request_id, playbook_id, summary, product_ids, "
        "image_embedding, text_embedding) values (%s, %s, 'wear_protection', 'abrasion on chute', "
        "%s, %s::extensions.vector, %s::extensions.vector) returning id",
        (t, r, [w["product"]], vec(512), vec(384)),
    )
    w["chat"] = insert(
        db,
        "chat_messages",
        tenant_id=t,
        request_id=r,
        role="assistant",
        body="The diagnosis is abrasion.",
    )
    w["proposal"] = insert(
        db,
        "knowledge_proposals",
        tenant_id=t,
        request_id=r,
        kind="product_value",
        target={"code": "wp-test"},
        change={"field": "max_service_temp_c"},
        proposed_by="chat",
    )
    w["event"] = insert(db, "events", tenant_id=t, request_id=r, type="request_created", payload={})
    return w


# --- one row per table ------------------------------------------------------------------


def test_the_schema_has_exactly_the_spec_tables(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'public' and table_type = 'BASE TABLE'"
    ).fetchall()
    assert {r[0] for r in rows} == TABLES


def test_one_row_per_table_inserts_and_reads_back(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    for table in TABLES:
        query = sql.SQL("select count(*) from {}").format(sql.Identifier(table))
        count = db.execute(query).fetchone()
        assert count is not None
        assert count[0] >= 1, table
    row = db.execute(
        "select r.status, r.priority, r.attempt, r.answers, p.name "
        "from requests r join plants p on p.id = r.plant_id where r.id = %s",
        (world["request"],),
    ).fetchone()
    assert row == ("submitted", "normal", 0, {"temperature": "ambient"}, "Plant 1")


# --- the rules the schema enforces (decision 0022) ----------------------------------------


def test_a_child_row_cannot_point_at_another_tenants_parent(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    other = insert(db, "tenants", name="Supplier B")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        # A tenant-B plant under tenant A's customer must be refused.
        insert(db, "plants", tenant_id=other, customer_id=world["customer"], name="Sneaky")


@pytest.mark.parametrize(
    ("statement", "row"),
    [
        ("update requests set status = 'teleported' where id = %s", "request"),
        ("update requests set priority = 'whenever' where id = %s", "request"),
        ("update products set status = 'maybe' where id = %s", "product"),
        ("update rules set status = 'maybe' where id = %s", "rule"),
        ("update pipeline_runs set status = 'kind of' where id = %s", "run"),
        ("update analyses set confidence = 1.5 where id = %s", "analysis"),
        ("update analyses set attempt = 0 where id = %s", "analysis"),
        ("update outcomes set reported_life_days = -1 where id = %s", "outcome"),
        ("update plant_invites set uses = max_uses + 1 where id = %s", "invite"),
        ("update profiles set roles = '{}' where user_id = %s", "user"),
        ("update profiles set roles = '{wizard}' where user_id = %s", "user"),
    ],
)
def test_invalid_values_are_refused(
    db: psycopg.Connection, world: dict[str, Any], statement: LiteralString, row: str
) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(statement, (world[row],))


def test_deleting_a_referenced_row_is_blocked(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("delete from plants where id = %s", (world["plant"],))


def test_updated_at_is_maintained_by_the_database(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    db.execute("update requests set updated_at = '2000-01-01' where id = %s", (world["request"],))
    db.execute("update requests set note = 'changed' where id = %s", (world["request"],))
    row = db.execute(
        "select updated_at > now() - interval '1 minute' from requests where id = %s",
        (world["request"],),
    ).fetchone()
    assert row == (True,)


def test_row_level_security_is_on_for_every_table(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    ).fetchall()
    assert rows == []


def test_every_vector_column_has_the_right_size_and_an_hnsw_index(db: psycopg.Connection) -> None:
    for table, column, dim in VECTOR_COLUMNS:
        typ = db.execute(
            "select format_type(atttypid, atttypmod) from pg_attribute "
            "where attrelid = %s::regclass and attname = %s",
            (f"public.{table}", column),
        ).fetchone()
        assert typ == (f"extensions.vector({dim})",) or typ == (f"vector({dim})",), (table, typ)
        index = db.execute(
            "select indexdef from pg_indexes where schemaname = 'public' and tablename = %s "
            "and indexdef ilike '%%using hnsw%%' and indexdef ilike %s",
            (table, f"%({column} %"),
        ).fetchone()
        assert index is not None, f"no HNSW index on {table}.{column}"
        assert "vector_cosine_ops" in index[0]


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("requests", "(tenant_id, status)"),
        ("products", "(tenant_id, family, status)"),
        ("rules", "(tenant_id, playbook_id, status)"),
    ],
)
def test_lookup_indexes_from_the_spec_exist(
    db: psycopg.Connection, table: str, columns: str
) -> None:
    rows = db.execute(
        "select indexdef from pg_indexes where schemaname = 'public' and tablename = %s", (table,)
    ).fetchall()
    assert any(columns in r[0] for r in rows), (table, columns)


def test_the_request_queues_exist(db: psycopg.Connection) -> None:
    rows = db.execute("select queue_name from pgmq.list_queues()").fetchall()
    assert {"requests", "requests_dlq"} <= {r[0] for r in rows}


def test_every_attempt_keeps_its_own_analysis(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    # Re-analysis (e.g. after the technician answers a question) adds a row; nothing is replaced.
    insert(db, "analyses", request_id=world["request"], attempt=2, tenant_id=world["tenant"])
    attempts = db.execute(
        "select attempt from analyses where request_id = %s order by attempt", (world["request"],)
    ).fetchall()
    assert attempts == [(1,), (2,)]


def test_one_attempt_can_never_get_a_second_analysis(
    db: psycopg.Connection, world: dict[str, Any]
) -> None:
    # Running the same attempt twice must never create a duplicate (CLAUDE.md invariant 4).
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert(db, "analyses", request_id=world["request"], attempt=1, tenant_id=world["tenant"])

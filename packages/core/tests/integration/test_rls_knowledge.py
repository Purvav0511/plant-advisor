"""Who sees which components, installations and knowledge (PLAN 1.3.d).

Staff see everything at their supplier, drafts included. Plant users see the components
and installations at their plants, and only *approved* knowledge (product names and
playbook questions), never drafts, rules or ingestion issues.
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


def visible(
    db: psycopg.Connection, as_user: Callable[[uuid.UUID], None], user: Any, table: str
) -> set[Any]:
    as_user(user)
    query = sql.SQL("select id from {}").format(sql.Identifier(table))
    rows = {r[0] for r in db.execute(query).fetchall()}
    db.execute("reset role")
    return rows


def playbook_versions(
    db: psycopg.Connection, as_user: Callable[[uuid.UUID], None], user: Any
) -> set[tuple[Any, int]]:
    as_user(user)
    rows = {(r[0], r[1]) for r in db.execute("select tenant_id, version from playbooks").fetchall()}
    db.execute("reset role")
    return rows


# --- components and installations --------------------------------------------------------


@pytest.mark.parametrize("table", ["components", "installations"])
@pytest.mark.parametrize("person", STAFF)
def test_staff_see_every_component_and_installation(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    person: str,
) -> None:
    prefix = "component" if table == "components" else "installation"
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], table) == {w[f"{prefix}_p1"], w[f"{prefix}_p2"]}


@pytest.mark.parametrize("table", ["components", "installations"])
@pytest.mark.parametrize(("person", "plant"), PLANT_USERS.items())
def test_plant_users_see_only_their_plants_components_and_installations(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    person: str,
    plant: str,
) -> None:
    prefix = "component" if table == "components" else "installation"
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], table) == {w[f"{prefix}_{plant}"]}


# --- knowledge: approved for everyone, drafts for staff ----------------------------------


@pytest.mark.parametrize(
    ("table", "prefix"),
    [("vocab_terms", "vocab"), ("products", "product"), ("product_images", "image")],
)
@pytest.mark.parametrize(
    ("person", "statuses"),
    [
        *[(p, ["approved", "draft"]) for p in STAFF],
        ("plant_user", ["approved"]),
        ("plant_user_p2", ["approved"]),
    ],
)
def test_knowledge_is_approved_only_for_plant_users(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    prefix: str,
    person: str,
    statuses: list[str],
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], table) == {w[f"{prefix}_{s}"] for s in statuses}


@pytest.mark.parametrize(
    ("person", "versions"),
    [*[(p, {1, 2}) for p in STAFF], ("plant_user", {1}), ("plant_user_p2", {1})],
)
def test_playbooks_are_approved_only_for_plant_users(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    person: str,
    versions: set[int],
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        # Version 1 is approved, version 2 a draft (conftest build_supplier).
        expected = {(w["tenant"], v) for v in versions}
        assert playbook_versions(db, as_user, w[person]) == expected


@pytest.mark.parametrize(("table", "key"), [("rules", "rule"), ("ingestion_issues", "issue")])
@pytest.mark.parametrize("person", [*STAFF, *PLANT_USERS])
def test_rules_and_ingestion_issues_are_staff_only(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    table: str,
    key: str,
    person: str,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        expected = {w[key]} if person in STAFF else set()
        assert visible(db, as_user, w[person], table) == expected

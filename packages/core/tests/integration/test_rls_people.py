"""Who sees which suppliers, customers, plants, people and invites (PLAN 1.3.c).

Each test signs in as one person from the two-supplier world (conftest `suppliers`) and
compares the rows they can see with the rows they should see. Nobody ever sees the other
supplier's rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.abc import Query

pytestmark = pytest.mark.integration

World = dict[str, dict[str, Any]]
STAFF = ["engineer", "sales", "admin"]
EVERYONE = ["plant_user", "plant_user_p2", "engineer", "sales", "admin", "staff_off_request"]


def visible(
    db: psycopg.Connection, as_user: Callable[[uuid.UUID], None], user: Any, query: Query
) -> set[Any]:
    """The keys `query` returns when run as `user`, then back to server mode."""
    as_user(user)
    rows = {r[0] for r in db.execute(query).fetchall()}
    db.execute("reset role")
    return rows


@pytest.mark.parametrize("person", EVERYONE)
def test_everyone_sees_only_their_own_supplier(
    db: psycopg.Connection, suppliers: World, as_user: Callable[[uuid.UUID], None], person: str
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], "select id from tenants") == {w["tenant"]}


@pytest.mark.parametrize(
    ("person", "sees_other_customer"),
    [
        *[(p, True) for p in [*STAFF, "staff_off_request"]],
        ("plant_user", False),
        ("plant_user_p2", False),
    ],
)
def test_customers_staff_see_all_plant_users_only_their_own(
    db: psycopg.Connection,
    suppliers: World,
    insert: Callable[..., Any],
    as_user: Callable[[uuid.UUID], None],
    person: str,
    sees_other_customer: bool,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        # A second customer that owns none of the plant users' plants.
        other = insert("customers", tenant_id=w["tenant"], name=f"Other {name}")
        expected = {w["customer"], other} if sees_other_customer else {w["customer"]}
        assert visible(db, as_user, w[person], "select id from customers") == expected


@pytest.mark.parametrize(
    ("person", "plants"),
    [
        *[(p, ["p1", "p2"]) for p in [*STAFF, "staff_off_request"]],
        ("plant_user", ["p1"]),
        ("plant_user_p2", ["p2"]),
    ],
)
def test_plants_staff_see_all_plant_users_only_theirs(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    person: str,
    plants: list[str],
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        assert visible(db, as_user, w[person], "select id from plants") == {w[p] for p in plants}


@pytest.mark.parametrize("person", [*STAFF, "staff_off_request"])
def test_staff_see_everyone_at_their_supplier(
    db: psycopg.Connection, suppliers: World, as_user: Callable[[uuid.UUID], None], person: str
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        seen = visible(db, as_user, w[person], "select user_id from profiles")
        assert seen == {w[p] for p in EVERYONE}


def test_plant_users_see_themselves_and_the_staff_on_their_requests(
    db: psycopg.Connection, suppliers: World, as_user: Callable[[uuid.UUID], None]
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        # p1's request: sales is the contact, the engineer wrote a message.
        p1 = visible(db, as_user, w["plant_user"], "select user_id from profiles")
        assert p1 == {w["plant_user"], w["sales"], w["engineer"]}
        # p2's request: no contact; the engineer wrote a message.
        p2 = visible(db, as_user, w["plant_user_p2"], "select user_id from profiles")
        assert p2 == {w["plant_user_p2"], w["engineer"]}


def test_the_engineer_who_claims_a_request_becomes_visible_to_its_plant_users(
    db: psycopg.Connection, suppliers: World, as_user: Callable[[uuid.UUID], None]
) -> None:
    w = suppliers["a"]
    db.execute("select set_config('app.transition', 'on', true)")
    db.execute("update requests set claimed_by = %s where id = %s", (w["admin"], w["request_p1"]))
    db.execute("select set_config('app.transition', 'off', true)")
    assert w["admin"] in visible(db, as_user, w["plant_user"], "select user_id from profiles")


@pytest.mark.parametrize(
    ("person", "sees_invite"),
    [("admin", True), ("engineer", False), ("sales", False), ("plant_user", False)],
)
def test_only_admins_see_invites(
    db: psycopg.Connection,
    suppliers: World,
    as_user: Callable[[uuid.UUID], None],
    person: str,
    sees_invite: bool,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        expected = {w["invite"]} if sees_invite else set()
        assert visible(db, as_user, w[person], "select id from plant_invites") == expected


@pytest.mark.parametrize("table", ["tenants", "customers", "plants", "profiles", "plant_invites"])
def test_a_user_without_a_profile_sees_nothing(
    db: psycopg.Connection, suppliers: World, as_user: Callable[[uuid.UUID], None], table: str
) -> None:
    stranger = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (stranger,))
    query = sql.SQL("select 1 from {}").format(sql.Identifier(table))
    assert visible(db, as_user, stranger, query) == set()

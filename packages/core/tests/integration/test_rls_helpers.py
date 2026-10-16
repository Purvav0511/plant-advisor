"""Integration tests for the "who am I" helpers the RLS policies use (PLAN 1.3.b).

They live in the `private` schema (not reachable from outside) and read the caller's
profile with the owner's rights, so a policy on `profiles` can use them without looping.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.integration

HELPERS = (
    "select private.my_tenant(), private.my_roles(), private.my_plants(), "
    "private.is_staff(), private.is_admin()"
)


def who_am_i(db: psycopg.Connection) -> tuple[Any, ...]:
    row = db.execute(HELPERS).fetchone()
    assert row is not None
    return tuple(row)


@pytest.mark.parametrize(
    ("person", "roles", "plants", "staff", "admin"),
    [
        ("plant_user", ["plant_user"], ["p1"], False, False),
        ("engineer", ["engineer"], [], True, False),
        ("sales", ["sales"], [], True, False),
        ("admin", ["admin"], [], True, True),
    ],
)
def test_each_person_sees_their_own_supplier_roles_and_plants(
    db: psycopg.Connection,
    suppliers: dict[str, dict[str, Any]],
    as_user: Callable[[uuid.UUID], None],
    person: str,
    roles: list[str],
    plants: list[str],
    staff: bool,
    admin: bool,
) -> None:
    for name in ("a", "b"):
        w = suppliers[name]
        as_user(w[person])
        assert who_am_i(db) == (w["tenant"], roles, [w[p] for p in plants], staff, admin)


def test_a_user_without_a_profile_gets_nothing(
    db: psycopg.Connection, as_user: Callable[[uuid.UUID], None]
) -> None:
    stranger = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (stranger,))
    as_user(stranger)
    assert who_am_i(db) == (None, [], [], False, False)


def test_signed_out_visitors_cannot_use_the_helpers(db: psycopg.Connection) -> None:
    db.execute("set local role anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(HELPERS)

"""Integration tests for transition_request() and the events trail (PLAN 1.2, SPEC §6).

Who may make each move is decided by the database from the caller's login (decision 0013,
update 2026-10-15): people are identified by their sign-in token, server code names itself
`worker` or `system`. Error codes: 42501 not permitted, P0001 move not allowed, P0002 unknown.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, LiteralString

import psycopg
import pytest
from dbtools import Insert, database_url, insert_row, set_server, set_user
from psycopg import sql

pytestmark = pytest.mark.integration

# SPEC §6: (from, to, who). "claimer" is the engineer who claimed the request.
ALLOWED = [
    ("submitted", "analyzing", "worker"),
    ("analyzing", "needs_info", "worker"),
    ("needs_info", "analyzing", "plant_user"),
    ("analyzing", "ready_for_review", "worker"),
    ("analyzing", "failed", "worker"),
    ("failed", "ready_for_review", "engineer"),
    ("ready_for_review", "in_review", "engineer"),
    ("in_review", "ready_for_review", "claimer"),
    ("in_review", "quote_sent", "sales"),
    ("in_review", "closed", "engineer"),
    ("in_review", "closed", "sales"),
    ("quote_sent", "closed", "sales"),
    ("quote_sent", "closed", "system"),
    # Admins may do anything engineers and sales may.
    ("failed", "ready_for_review", "admin"),
    ("ready_for_review", "in_review", "admin"),
    ("in_review", "ready_for_review", "admin"),
    ("in_review", "quote_sent", "admin"),
    ("in_review", "closed", "admin"),
    ("quote_sent", "closed", "admin"),
]


# --- setup -----------------------------------------------------------------------------


def add_user(
    db: psycopg.Connection,
    insert: Insert,
    tenant: Any,
    roles: list[str],
    plant_ids: list[Any] | None = None,
) -> uuid.UUID:
    user = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (user,))
    insert("profiles", user_id=user, tenant_id=tenant, roles=roles, plant_ids=plant_ids or [])
    return user


@pytest.fixture
def cast(db: psycopg.Connection, insert: Insert) -> dict[str, Any]:
    """One supplier with a plant, a component, a request, and everyone who acts on it."""
    c: dict[str, Any] = {}
    c["tenant"] = t = insert("tenants", name="Supplier A")
    customer = insert("customers", tenant_id=t, name="Cement Co")
    c["plant"] = insert("plants", tenant_id=t, customer_id=customer, name="Plant A")
    c["other_plant"] = insert("plants", tenant_id=t, customer_id=customer, name="Plant B")
    component = insert(
        "components",
        tenant_id=t,
        plant_id=c["plant"],
        playbook_id="wear_protection",
        component_type="chute",
        name="Chute",
    )
    c["plant_user"] = add_user(db, insert, t, ["plant_user"], [c["plant"]])
    c["other_plant_user"] = add_user(db, insert, t, ["plant_user"], [c["other_plant"]])
    c["engineer"] = add_user(db, insert, t, ["engineer"])
    c["engineer2"] = add_user(db, insert, t, ["engineer"])
    c["sales"] = add_user(db, insert, t, ["sales"])
    c["admin"] = add_user(db, insert, t, ["admin"])
    other_tenant = insert("tenants", name="Supplier B")
    c["foreign_engineer"] = add_user(db, insert, other_tenant, ["engineer"])
    c["request"] = insert(
        "requests",
        tenant_id=t,
        customer_id=customer,
        plant_id=c["plant"],
        component_id=component,
        playbook_id="wear_protection",
        created_by=c["plant_user"],
    )
    return c


def force_status(db: psycopg.Connection, request: Any, status: str, **columns: Any) -> None:
    """Test setup only: put a request into a state, as trusted server code. Uses the same
    transaction flag as transition_request(), which only the database owner can do."""
    values = {"status": status, **columns}
    query = sql.SQL("update requests set {assignments} where id = %s").format(
        assignments=sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(name)) for name in values
        )
    )
    db.execute("select set_config('app.transition', 'on', true)")
    db.execute(query, (*values.values(), request))
    db.execute("select set_config('app.transition', 'off', true)")


def transition(
    db: psycopg.Connection,
    cast: dict[str, Any],
    request: Any,
    to: str,
    who: str,
    reason: str | None = None,
) -> str:
    """Call transition_request() as `who`: a person from `cast`, or `worker` / `system`."""
    if who in ("worker", "system"):
        set_server(db)
        row = db.execute(
            "select (transition_request(%s, %s, %s, %s)).status", (request, to, who, reason)
        ).fetchone()
    else:
        set_user(db, cast[who])
        row = db.execute(
            "select (transition_request(%s, %s, null, %s)).status", (request, to, reason)
        ).fetchone()
        set_server(db)
    assert row is not None
    return row[0]


def request_row(db: psycopg.Connection, request: Any) -> tuple[Any, ...]:
    row = db.execute(
        "select status, attempt, claimed_by from requests where id = %s", (request,)
    ).fetchone()
    assert row is not None
    return tuple(row)


def last_event(db: psycopg.Connection, request: Any) -> tuple[Any, ...]:
    row = db.execute(
        "select type, payload from events where request_id = %s order by id desc limit 1",
        (request,),
    ).fetchone()
    assert row is not None
    return tuple(row)


def prepare(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert, frm: str, to: str
) -> None:
    """Put the request in `frm`, with what each move needs (a claim, an approved review)."""
    request = cast["request"]
    if frm == "in_review":
        force_status(db, request, frm, claimed_by=cast["engineer"])
    else:
        force_status(db, request, frm)
    if to == "quote_sent":
        insert(
            "reviews",
            tenant_id=cast["tenant"],
            request_id=request,
            engineer_id=cast["engineer"],
            decision="approved",
        )


# --- every allowed move ------------------------------------------------------------------


@pytest.mark.parametrize(("frm", "to", "who"), ALLOWED)
def test_every_allowed_move_succeeds_and_is_logged(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert, frm: str, to: str, who: str
) -> None:
    prepare(db, cast, insert, frm, to)
    actor = "engineer" if who == "claimer" else who
    assert transition(db, cast, cast["request"], to, actor, reason="test") == to
    kind, payload = last_event(db, cast["request"])
    assert kind == "status_changed"
    assert payload["from"] == frm
    assert payload["to"] == to
    assert payload["reason"] == "test"
    if actor in ("worker", "system"):
        assert payload["actor"] == actor
        assert payload["actor_id"] is None
    else:
        assert payload["actor"] == "user"
        assert payload["actor_id"] == str(cast[actor])


# --- moves that aren't in the table ------------------------------------------------------


@pytest.mark.parametrize(
    ("frm", "to", "who"),
    [
        ("submitted", "quote_sent", "admin"),
        ("submitted", "ready_for_review", "worker"),
        ("closed", "analyzing", "worker"),
        ("quote_sent", "in_review", "admin"),
        ("ready_for_review", "closed", "admin"),
        ("needs_info", "ready_for_review", "worker"),
        ("failed", "closed", "admin"),
        ("closed", "closed", "admin"),
        ("analyzing", "analyzing", "worker"),
    ],
)
def test_moves_outside_the_table_are_refused(
    db: psycopg.Connection, cast: dict[str, Any], frm: str, to: str, who: str
) -> None:
    force_status(db, cast["request"], frm)
    with pytest.raises(psycopg.errors.RaiseException, match="not allowed"):
        transition(db, cast, cast["request"], to, who)


# --- the right move by the wrong caller --------------------------------------------------


@pytest.mark.parametrize(
    ("frm", "to", "who"),
    [
        ("ready_for_review", "in_review", "worker"),
        ("ready_for_review", "in_review", "plant_user"),
        ("ready_for_review", "in_review", "sales"),
        ("in_review", "quote_sent", "engineer"),
        ("in_review", "quote_sent", "plant_user"),
        ("in_review", "ready_for_review", "engineer2"),
        ("needs_info", "analyzing", "other_plant_user"),
        ("needs_info", "analyzing", "engineer"),
        ("needs_info", "analyzing", "worker"),
        ("submitted", "analyzing", "engineer"),
        ("analyzing", "ready_for_review", "admin"),
        ("quote_sent", "closed", "worker"),
        ("failed", "ready_for_review", "system"),
    ],
)
def test_the_wrong_caller_is_refused(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert, frm: str, to: str, who: str
) -> None:
    prepare(db, cast, insert, frm, to)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        transition(db, cast, cast["request"], to, who)


def test_another_suppliers_staff_cannot_even_see_the_request(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    # "Not found", not "not permitted": the answer mustn't reveal which request IDs exist.
    force_status(db, cast["request"], "ready_for_review")
    with pytest.raises(psycopg.errors.NoDataFound):
        transition(db, cast, cast["request"], "in_review", "foreign_engineer")


def test_a_signed_in_user_cannot_pose_as_the_worker(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    set_user(db, cast["engineer"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select transition_request(%s, 'analyzing', 'worker', null)", (cast["request"],))


@pytest.mark.parametrize("actor", [None, "engineer", "robot"])
def test_server_code_must_name_itself_worker_or_system(
    db: psycopg.Connection, cast: dict[str, Any], actor: str | None
) -> None:
    set_server(db)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select transition_request(%s, 'analyzing', %s, null)", (cast["request"], actor))


def test_a_user_without_a_profile_is_refused(db: psycopg.Connection, cast: dict[str, Any]) -> None:
    stranger = uuid.uuid4()
    db.execute("insert into auth.users (id) values (%s)", (stranger,))
    set_user(db, stranger)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("select transition_request(%s, 'analyzing', null, null)", (cast["request"],))


def test_an_unknown_request_is_not_found(db: psycopg.Connection) -> None:
    set_server(db)
    with pytest.raises(psycopg.errors.NoDataFound):
        db.execute("select transition_request(%s, 'analyzing', 'worker', null)", (uuid.uuid4(),))


def test_an_unknown_status_is_not_allowed(db: psycopg.Connection, cast: dict[str, Any]) -> None:
    set_server(db)
    with pytest.raises(psycopg.errors.RaiseException, match="not allowed"):
        db.execute(
            "select transition_request(%s, 'teleported', 'worker', null)", (cast["request"],)
        )


# --- the special rules -------------------------------------------------------------------


def test_claim_records_the_engineer_and_release_clears_it(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    request = cast["request"]
    force_status(db, request, "ready_for_review")
    transition(db, cast, request, "in_review", "engineer")
    assert request_row(db, request)[2] == cast["engineer"]
    transition(db, cast, request, "ready_for_review", "engineer")
    assert request_row(db, request)[2] is None


@pytest.mark.parametrize("decision", [None, "rejected"])
def test_a_quote_needs_an_approved_or_edited_review(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert, decision: str | None
) -> None:
    request = cast["request"]
    force_status(db, request, "in_review", claimed_by=cast["engineer"])
    if decision:
        insert(
            "reviews",
            tenant_id=cast["tenant"],
            request_id=request,
            engineer_id=cast["engineer"],
            decision=decision,
        )
    with pytest.raises(psycopg.errors.RaiseException, match="approved or edited review"):
        transition(db, cast, request, "quote_sent", "sales")


def test_an_edited_review_also_allows_the_quote(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert
) -> None:
    request = cast["request"]
    force_status(db, request, "in_review", claimed_by=cast["engineer"])
    insert(
        "reviews",
        tenant_id=cast["tenant"],
        request_id=request,
        engineer_id=cast["engineer"],
        decision="edited",
    )
    assert transition(db, cast, request, "quote_sent", "sales") == "quote_sent"


def test_each_entry_into_analyzing_starts_a_new_attempt(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    request = cast["request"]
    assert request_row(db, request)[1] == 0
    transition(db, cast, request, "analyzing", "worker")
    assert request_row(db, request)[1] == 1
    transition(db, cast, request, "needs_info", "worker", reason="question:impact")
    transition(db, cast, request, "analyzing", "plant_user")
    assert request_row(db, request)[1] == 2


def test_creating_a_request_logs_it(db: psycopg.Connection, cast: dict[str, Any]) -> None:
    row = db.execute(
        "select type, payload from events where request_id = %s order by id limit 1",
        (cast["request"],),
    ).fetchone()
    assert row is not None
    assert row[0] == "request_created"
    assert row[1]["created_by"] == str(cast["plant_user"])


# --- the two locks: nothing else can change the status -----------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "update requests set status = 'closed' where id = %s",
        "update requests set attempt = 7 where id = %s",
        "update requests set claimed_by = created_by where id = %s",
    ],
)
def test_server_code_cannot_change_lifecycle_columns_directly(
    db: psycopg.Connection, cast: dict[str, Any], statement: LiteralString
) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="transition_request"):
        db.execute(statement, (cast["request"],))


@pytest.mark.parametrize(
    ("column", "value"),
    [("status", "closed"), ("attempt", 3), ("claimed_by", "creator")],
)
def test_a_new_request_must_start_submitted_unclaimed_at_attempt_zero(
    db: psycopg.Connection, cast: dict[str, Any], insert: Insert, column: str, value: Any
) -> None:
    row = db.execute(
        "select tenant_id, customer_id, plant_id, component_id, created_by "
        "from requests where id = %s",
        (cast["request"],),
    ).fetchone()
    assert row is not None
    tenant, customer, plant, component, creator = row
    with pytest.raises(psycopg.errors.RaiseException, match="must start"):
        insert(
            "requests",
            tenant_id=tenant,
            customer_id=customer,
            plant_id=plant,
            component_id=component,
            playbook_id="wear_protection",
            created_by=creator,
            **{column: creator if value == "creator" else value},
        )


def test_signed_in_users_cannot_change_the_status_even_with_the_flag(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    set_user(db, cast["admin"])
    db.execute("select set_config('app.transition', 'on', true)")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("update requests set status = 'closed' where id = %s", (cast["request"],))


def test_the_flag_is_off_again_after_a_transition(
    db: psycopg.Connection, cast: dict[str, Any]
) -> None:
    transition(db, cast, cast["request"], "analyzing", "worker")
    with pytest.raises(psycopg.errors.RaiseException, match="transition_request"):
        db.execute("update requests set status = 'closed' where id = %s", (cast["request"],))


# --- two engineers claiming at the same moment -------------------------------------------


def test_two_simultaneous_claims_leave_exactly_one_winner() -> None:
    """Uses committed data and two real connections, so it builds its own world."""
    with psycopg.connect(database_url(), autocommit=True) as setup:
        t = insert_row(setup, "tenants", name="Race Co")
        customer = insert_row(setup, "customers", tenant_id=t, name="C")
        plant = insert_row(setup, "plants", tenant_id=t, customer_id=customer, name="P")
        component = insert_row(
            setup,
            "components",
            tenant_id=t,
            plant_id=plant,
            playbook_id="wear_protection",
            component_type="chute",
            name="X",
        )
        engineers = []
        for _ in range(2):
            user = uuid.uuid4()
            setup.execute("insert into auth.users (id) values (%s)", (user,))
            insert_row(setup, "profiles", user_id=user, tenant_id=t, roles=["engineer"])
            engineers.append(user)
        request = insert_row(
            setup,
            "requests",
            tenant_id=t,
            customer_id=customer,
            plant_id=plant,
            component_id=component,
            playbook_id="wear_protection",
            created_by=engineers[0],
        )
        with setup.transaction():
            force_status(setup, request, "ready_for_review")

    first = psycopg.connect(database_url())
    second = psycopg.connect(database_url())
    results: dict[str, str] = {}
    try:
        # First engineer claims and holds the lock (transaction still open).
        set_user(first, engineers[0])
        first.execute("select transition_request(%s, 'in_review', null, null)", (request,))

        def second_claim() -> None:
            try:
                set_user(second, engineers[1])
                second.execute("select transition_request(%s, 'in_review', null, null)", (request,))
                second.commit()
                results["second"] = "won"
            except psycopg.errors.RaiseException:
                second.rollback()
                results["second"] = "refused"

        racer = threading.Thread(target=second_claim)
        racer.start()
        racer.join(timeout=1)
        assert racer.is_alive(), "the second claim should wait for the first one's lock"
        first.commit()
        racer.join(timeout=10)
        assert results == {"second": "refused"}
    finally:
        first.close()
        second.close()

    with psycopg.connect(database_url()) as check:
        row = check.execute(
            "select status, claimed_by from requests where id = %s", (request,)
        ).fetchone()
        assert row == ("in_review", engineers[0])

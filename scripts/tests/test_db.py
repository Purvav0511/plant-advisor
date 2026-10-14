import pytest

from scripts import db
from scripts.db import RepoState, is_local_url, remote_migrate_problems

READY = RepoState(branch="dev", dirty=False, fetched=True, ahead=0, behind=0)


def test_is_local_url():
    assert is_local_url("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    assert is_local_url("postgresql://u:p@localhost/db")
    assert not is_local_url(
        "postgresql://postgres.ref:pw@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
    )
    assert not is_local_url("")


def test_remote_migrate_allowed_only_from_a_clean_dev_that_matches_github():
    assert remote_migrate_problems(READY) == []


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (READY._replace(branch="task/0.4-local-supabase"), "only from `dev`"),
        (READY._replace(branch="main"), "only from `dev`"),
        (READY._replace(dirty=True), "uncommitted changes"),
        (READY._replace(fetched=False), "couldn't reach GitHub"),
        (READY._replace(behind=2), "2 commit(s) behind"),
        (READY._replace(ahead=1), "1 commit(s) that aren't on GitHub"),
    ],
)
def test_remote_migrate_refusals(state, expected):
    problems = remote_migrate_problems(state)
    assert any(expected in p for p in problems), problems


def test_remote_migrate_reports_every_problem_at_once():
    state = RepoState(branch="task/x", dirty=True, fetched=False, ahead=1, behind=1)
    # Branch, dirty and fetch: the ahead/behind counts are meaningless after a failed fetch.
    assert len(remote_migrate_problems(state)) == 3


def test_migrate_refuses_without_calling_supabase(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@remote.example.com/postgres")
    monkeypatch.setattr(db, "repo_state", lambda: READY._replace(branch="task/x"))
    monkeypatch.setattr(db, "supabase", lambda args: calls.append(args) or 0)
    assert db.migrate([]) == 1
    assert calls == []


def test_migrate_runs_when_everything_checks_out(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@remote.example.com/postgres")
    monkeypatch.setattr(db, "repo_state", lambda: READY)
    monkeypatch.setattr(db, "supabase", lambda args: calls.append(args) or 0)
    assert db.migrate([]) == 0
    assert calls == [
        ["migration", "up", "--db-url", "postgresql://u:p@remote.example.com/postgres"]
    ]


def test_migrate_local_skips_the_remote_checks(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "repo_state", lambda: pytest.fail("checked the repo for --local"))
    monkeypatch.setattr(db, "supabase", lambda args: calls.append(args) or 0)
    assert db.migrate(["--local"]) == 0
    assert calls == [["migration", "up", "--local"]]


def test_wrong_branch_skips_the_ahead_behind_comparison():
    # Ahead/behind compares HEAD with GitHub's `dev`, which only means something on `dev`.
    problems = remote_migrate_problems(READY._replace(branch="task/x", ahead=1, behind=3))
    assert len(problems) == 1
    assert "only from `dev`" in problems[0]

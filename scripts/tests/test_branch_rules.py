import pytest

from scripts.branch_rules import checks_passing, is_protected, merge_plan, owner_has_read
from scripts.guard_branch import main as guard_main
from scripts.merge import rollup_conclusions
from scripts.verify_push import find_merged_pr, head_check_conclusions


@pytest.mark.parametrize(
    ("base", "head", "method"),
    [
        ("dev", "task/0.3-ci", "squash"),
        ("dev", "fix/typo", "squash"),
        ("dev", "dependabot/uv/ruff-0.18", "squash"),
        ("dev", "main", "merge"),
        ("main", "dev", "merge"),
        ("main", "hotfix/broken-upload", "merge"),
    ],
)
def test_allowed_merges(base, head, method):
    plan = merge_plan(base, head)
    assert plan is not None
    assert plan.method == method


@pytest.mark.parametrize(
    ("base", "head"),
    [
        ("main", "task/0.3-ci"),
        ("main", "fix/typo"),
        ("dev", "hotfix/x"),
        ("dev", "random-branch"),
        ("feature", "task/x"),
    ],
)
def test_forbidden_merges(base, head):
    assert merge_plan(base, head) is None


def test_hotfix_reminds_about_back_merge():
    plan = merge_plan("main", "hotfix/x")
    assert plan is not None
    assert plan.reminder is not None
    assert "main -> dev" in plan.reminder


def test_protected_branches():
    assert is_protected("main")
    assert is_protected("dev")
    assert not is_protected("task/0.3-ci")


def test_checks_passing():
    assert checks_passing(["SUCCESS", "skipped", "NEUTRAL"])[0]
    assert not checks_passing([])[0]
    assert not checks_passing(["SUCCESS", "FAILURE"])[0]
    assert not checks_passing(["SUCCESS", None])[0]


def test_rollup_conclusions_handles_check_runs_and_statuses():
    rollup = [
        {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": ""},
        {"__typename": "StatusContext", "state": "FAILURE"},
    ]
    assert rollup_conclusions(rollup) == ["SUCCESS", "IN_PROGRESS", "FAILURE"]


def test_find_merged_pr_matches_merge_commit_and_base():
    pulls = [
        {"merged_at": None, "merge_commit_sha": "abc", "base": {"ref": "dev"}},
        {"merged_at": "2026-10-13", "merge_commit_sha": "abc", "base": {"ref": "main"}},
        {"merged_at": "2026-10-13", "merge_commit_sha": "abc", "base": {"ref": "dev"}, "n": 1},
    ]
    assert find_merged_pr(pulls, "abc", "dev") == pulls[2]
    assert find_merged_pr(pulls, "zzz", "dev") is None


def test_head_check_conclusions_skips_the_guard_and_reports_pending():
    runs = [
        {"name": "verify push", "status": "completed", "conclusion": "failure"},
        {"name": "lint and unit tests", "status": "completed", "conclusion": "success"},
        {"name": "web build", "status": "in_progress", "conclusion": None},
    ]
    assert head_check_conclusions(runs) == ["success", "in_progress"]


def test_push_guard_blocks_protected_targets(monkeypatch):
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/main")
    assert guard_main(["push"]) == 1
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/dev")
    assert guard_main(["push"]) == 1
    monkeypatch.setenv("PRE_COMMIT_REMOTE_BRANCH", "refs/heads/task/0.3-ci")
    assert guard_main(["push"]) == 0


def test_commit_guard_blocks_protected_branches(monkeypatch):
    monkeypatch.setattr("scripts.guard_branch.current_branch", lambda: "dev")
    assert guard_main(["commit"]) == 1
    monkeypatch.setattr("scripts.guard_branch.current_branch", lambda: "task/x")
    assert guard_main(["commit"]) == 0


def test_owner_has_read_needs_the_ticked_box():
    assert owner_has_read("intro\n- [x] I read every changed file and can explain it\n")
    assert owner_has_read("* [X] I read every changed file")
    assert not owner_has_read("- [ ] I read every changed file")
    assert not owner_has_read("I read every changed file")
    assert not owner_has_read(None)

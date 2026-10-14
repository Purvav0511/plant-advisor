"""CI guard for pushes to `main` and `dev` (decision 0019). Runs in `.github/workflows/guard.yml`.

Every commit that lands on a protected branch must be the merge commit of a PR that:
- the branch model allows (`scripts/branch_rules.py`), and
- had every check passing on its head commit.

If not, this exits non-zero and opens an issue, because without a paid GitHub plan
nothing can block the push itself.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from scripts._common import run_capture
from scripts.branch_rules import checks_passing, is_protected, merge_plan

GUARD_CHECK_NAME = "verify push"


def gh_json(args: list[str]) -> Any:
    proc = run_capture(["gh", *args], timeout=60)
    if proc is None or proc.returncode != 0:
        detail = proc.stderr.strip() if proc else "gh not found"
        raise RuntimeError(f"gh {' '.join(args)} failed: {detail}")
    return json.loads(proc.stdout)


def find_merged_pr(pulls: list[dict[str, Any]], sha: str, branch: str) -> dict[str, Any] | None:
    """The merged PR whose merge commit is `sha` and whose base is `branch`."""
    for pr in pulls:
        if (
            pr.get("merged_at")
            and pr.get("merge_commit_sha") == sha
            and pr.get("base", {}).get("ref") == branch
        ):
            return pr
    return None


def head_check_conclusions(check_runs: list[dict[str, Any]]) -> list[str | None]:
    """Conclusions of the PR head's check runs, ignoring this guard itself."""
    results: list[str | None] = []
    for run in check_runs:
        if run.get("name") == GUARD_CHECK_NAME:
            continue
        status = run.get("status")
        results.append(run.get("conclusion") if status == "completed" else status)
    return results


def verify(repo: str, sha: str, branch: str) -> list[str]:
    """Problems with this push; empty means it's fine."""
    if not is_protected(branch):
        return []
    pulls = gh_json(["api", f"repos/{repo}/commits/{sha}/pulls"])
    pr = find_merged_pr(pulls, sha, branch)
    if pr is None:
        return [f"`{sha[:12]}` on `{branch}` didn't come from a merged PR (direct push?)"]
    head = pr["head"]["ref"]
    problems: list[str] = []
    if merge_plan(branch, head) is None:
        problems.append(f"PR #{pr['number']} merged `{head}` into `{branch}`, which isn't allowed")
    runs = gh_json(["api", f"repos/{repo}/commits/{pr['head']['sha']}/check-runs?per_page=100"])
    ok, detail = checks_passing(head_check_conclusions(runs.get("check_runs", [])))
    if not ok:
        problems.append(f"PR #{pr['number']} was merged without green checks: {detail}")
    return problems


def open_issue(repo: str, sha: str, branch: str, problems: list[str]) -> None:
    body = "\n".join(
        [
            f"The push of `{sha}` to `{branch}` broke the branch rules (decision 0019):",
            "",
            *[f"- {p}" for p in problems],
            "",
            "Revert it through a PR, or fix forward through a PR with green checks.",
        ]
    )
    run_capture(
        ["gh", "issue", "create", "--repo", repo, "--title", f"Branch rule broken on {branch}",
         "--body", body],
        timeout=60,
    )  # fmt: skip


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    branch = os.environ["GITHUB_REF_NAME"]
    problems = verify(repo, sha, branch)
    if not problems:
        print(f"ok: `{sha[:12]}` on `{branch}` came from a merged PR with green checks")
        return 0
    for p in problems:
        print(f"::error::{p}")
    open_issue(repo, sha, branch, problems)
    return 1


if __name__ == "__main__":
    sys.exit(main())

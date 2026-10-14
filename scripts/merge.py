"""`uv run poe merge <pr-number>`: merge a PR only if the branch model allows it and CI is green.

A local stand-in for GitHub's required status checks (decision 0019). It uses the GitHub
CLI (`gh`), which must be signed in.
"""

from __future__ import annotations

import json
import sys

from scripts._common import run_capture, run_passthrough
from scripts.branch_rules import READ_CONFIRMATION, checks_passing, merge_plan, owner_has_read


def rollup_conclusions(rollup: list[dict[str, str]]) -> list[str | None]:
    """Normalize `statusCheckRollup` entries (check runs and commit statuses) to results."""
    results: list[str | None] = []
    for item in rollup:
        if item.get("__typename") == "StatusContext":
            results.append(item.get("state"))
        elif item.get("status") != "COMPLETED":
            results.append(item.get("status") or "PENDING")
        else:
            results.append(item.get("conclusion"))
    return results


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("usage: uv run poe merge <pr-number>")
        return 2
    number = argv[0]
    fields = "baseRefName,headRefName,state,isDraft,mergeable,statusCheckRollup,title,body"
    proc = run_capture(["gh", "pr", "view", number, "--json", fields])
    if proc is None or proc.returncode != 0:
        reason = proc.stderr.strip() if proc else "gh not found"
        print(f"error: couldn't read PR #{number} with `gh` ({reason})")
        return 1
    pr = json.loads(proc.stdout)
    base, head = pr["baseRefName"], pr["headRefName"]
    print(f"PR #{number}: {pr['title']}  ({head} -> {base})")

    if pr["state"] != "OPEN" or pr["isDraft"]:
        print(f"refusing: the PR is {'a draft' if pr['isDraft'] else pr['state'].lower()}")
        return 1
    plan = merge_plan(base, head)
    if plan is None:
        print(f"refusing: `{head}` may not merge into `{base}` (branch model, decision 0019)")
        return 1
    ok, detail = checks_passing(rollup_conclusions(pr["statusCheckRollup"]))
    if not ok:
        print(f"refusing: {detail}. Wait for CI or fix it first.")
        return 1
    if not owner_has_read(pr.get("body")):
        print(
            f"refusing: tick `- [x] {READ_CONFIRMATION}` in the PR description once you've read "
            "the code (ask `/walkthrough " + number + "` for a guided read)"
        )
        return 1
    if pr["mergeable"] == "CONFLICTING":
        print("refusing: the PR has merge conflicts")
        return 1

    print(f"{detail}; merging with a {plan.method} commit")
    code = run_passthrough(["gh", "pr", "merge", number, f"--{plan.method}", "--delete-branch"])
    if code == 0 and plan.reminder:
        print(plan.reminder)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

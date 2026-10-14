"""Git hooks that keep work off `main` and `dev` (decision 0019).

- `commit` (pre-commit stage): refuse commits made while `main` or `dev` is checked out.
- `push` (pre-push stage): refuse pushes to `main` or `dev`. Changes arrive through PRs.

These are local stand-ins for GitHub branch protection, which needs a paid plan for
private repos. The CI guard (`scripts/verify_push.py`) catches anything that slips past.
"""

from __future__ import annotations

import os
import sys

from scripts._common import run_capture
from scripts.branch_rules import PROTECTED, is_protected


def current_branch() -> str:
    proc = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return proc.stdout.strip() if proc and proc.returncode == 0 else ""


def remote_branch_from_env() -> str:
    # pre-commit sets this for pre-push hooks, e.g. "refs/heads/main".
    ref = os.environ.get("PRE_COMMIT_REMOTE_BRANCH", "")
    return ref.removeprefix("refs/heads/")


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "commit":
        branch = current_branch()
        if is_protected(branch):
            print(
                f"refusing to commit on `{branch}`: create a branch first, "
                "e.g. `git switch -c task/<id>-<slug>` (CLAUDE.md, decision 0019)"
            )
            return 1
        return 0
    if mode == "push":
        target = remote_branch_from_env()
        if is_protected(target):
            print(
                f"refusing to push to `{target}`: open a PR instead "
                f"({', '.join(PROTECTED)} only change through PRs; decision 0019)"
            )
            return 1
        return 0
    print("usage: python -m scripts.guard_branch commit|push")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

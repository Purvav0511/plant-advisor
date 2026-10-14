"""Branch model (decision 0019), shared by the git hooks, `poe merge` and the CI guard.

    task/* fix/* ──PR──▶ dev ──release PR──▶ main
    hotfix/* ──PR──▶ main, then a back-merge PR main ──▶ dev

`main` is production and `dev` is integration. Neither takes direct commits or pushes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

PROTECTED = ("main", "dev")

# A check run or status with one of these results doesn't block a merge.
PASSING = {"SUCCESS", "SKIPPED", "NEUTRAL"}


@dataclass(frozen=True)
class MergePlan:
    method: str  # "squash" or "merge"
    reminder: str | None = None


def is_protected(branch: str) -> bool:
    return branch in PROTECTED


def merge_plan(base: str, head: str) -> MergePlan | None:
    """How a PR from `head` into `base` merges, or None if the branch model forbids it.

    Feature work is squashed into dev, so each task is one commit. Releases and
    back-merges use merge commits, so main's tree stays identical to the tested dev tree.
    """
    if base == "dev":
        if head.startswith(("task/", "fix/", "dependabot/")):
            return MergePlan("squash")
        if head == "main":
            return MergePlan("merge")
        return None
    if base == "main":
        if head == "dev":
            return MergePlan("merge")
        if head.startswith("hotfix/"):
            return MergePlan(
                "merge",
                reminder="Hotfix merged into main: open a back-merge PR main -> dev now.",
            )
        return None
    return None


def checks_passing(conclusions: Iterable[str | None]) -> tuple[bool, str]:
    """Whether every check passed. An empty list doesn't count as passing."""
    values = [(c or "PENDING").upper() for c in conclusions]
    if not values:
        return False, "no checks have run"
    failing = [v for v in values if v not in PASSING]
    if failing:
        return False, f"{len(failing)} of {len(values)} checks not passing ({', '.join(failing)})"
    return True, f"all {len(values)} checks passing"

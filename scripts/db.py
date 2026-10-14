"""Database tasks: `uv run poe db-up | db-down | migrate [--local] | test-int`.

- Local Supabase (Docker) is only for integration tests (PLAN 0.4). It starts just the
  services the tests need.
- `migrate` without `--local` applies migrations to the shared hosted dev project. It only
  runs from a clean `dev` that matches GitHub exactly, so the shared database only ever
  gets reviewed, merged migrations. When it can't tell, it refuses.
- `reset` only ever targets the local database. Nothing here can reset a remote one.
"""

from __future__ import annotations

import os
import sys
from typing import NamedTuple
from urllib.parse import urlparse

from scripts._common import find_tool, run_capture, run_passthrough

# Containers the integration tests don't need. Kept: Postgres, auth (gotrue) and the
# API gateway (kong) that serves auth's JWKS for the token tests in PLAN 4.1.
EXCLUDED_SERVICES = [
    "realtime",
    "storage-api",
    "imgproxy",
    "mailpit",
    "postgrest",
    "postgres-meta",
    "studio",
    "edge-runtime",
    "logflare",
    "vector",
    "supavisor",
]

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# The only branch that may migrate the shared dev database (decision 0019).
MIGRATE_BRANCH = "dev"


class RepoState(NamedTuple):
    """What `migrate` needs to know about the local checkout."""

    branch: str
    dirty: bool  # uncommitted changes to tracked or new files
    fetched: bool  # whether `git fetch` reached GitHub just now
    ahead: int  # local commits not on GitHub
    behind: int  # GitHub commits not in the local branch


def is_local_url(url: str) -> bool:
    """Whether a Postgres URL points at this machine."""
    return (urlparse(url).hostname or "") in LOCAL_HOSTS


def supabase(args: list[str]) -> int:
    if find_tool("pnpm") is None:
        print("error: pnpm not found. Run `corepack enable` (DEV_SETUP §4).")
        return 127
    return run_passthrough(["pnpm", "exec", "supabase", *args])


def remote_migrate_problems(state: RepoState) -> list[str]:
    """Reasons not to migrate the shared database from this checkout; empty means go ahead."""
    problems: list[str] = []
    if state.branch != MIGRATE_BRANCH:
        problems.append(
            f"you're on `{state.branch}`; migrate the shared database only from `{MIGRATE_BRANCH}`"
            f" after the PR is merged (`git switch {MIGRATE_BRANCH} && git pull`)"
        )
    if state.dirty:
        problems.append("there are uncommitted changes; commit or stash them first")
    if not state.fetched:
        problems.append("couldn't reach GitHub to check you're up to date; try again online")
    elif state.branch == MIGRATE_BRANCH:
        # Ahead/behind compares HEAD with GitHub's `dev`, so it only means something on `dev`.
        if state.behind:
            problems.append(
                f"`{MIGRATE_BRANCH}` is {state.behind} commit(s) behind GitHub; run `git pull`"
            )
        if state.ahead:
            problems.append(
                f"`{MIGRATE_BRANCH}` has {state.ahead} commit(s) that aren't on GitHub; "
                "they must arrive through a merged PR"
            )
    return problems


def repo_state() -> RepoState:
    """Read the checkout's state, fetching `dev` from GitHub first."""
    branch_proc = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_proc.stdout.strip() if branch_proc and branch_proc.returncode == 0 else ""
    status = run_capture(["git", "status", "--porcelain"])
    dirty = status is None or status.returncode != 0 or bool(status.stdout.strip())
    fetch = run_capture(["git", "fetch", "--quiet", "origin", MIGRATE_BRANCH], timeout=60)
    fetched = fetch is not None and fetch.returncode == 0
    ahead = behind = 0
    if fetched:
        counts = run_capture(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{MIGRATE_BRANCH}"]
        )
        if counts is None or counts.returncode != 0:
            fetched = False
        else:
            ahead, behind = (int(n) for n in counts.stdout.split())
    return RepoState(branch=branch, dirty=dirty, fetched=fetched, ahead=ahead, behind=behind)


def up() -> int:
    return supabase(["start", "-x", ",".join(EXCLUDED_SERVICES)])


def down() -> int:
    return supabase(["stop"])


def reset_local() -> int:
    return supabase(["db", "reset", "--local"])


def migrate(argv: list[str]) -> int:
    if "--local" in argv:
        return supabase(["migration", "up", "--local"])
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("error: DATABASE_URL is empty. Fill it in .env (DEV_SETUP §5).")
        return 1
    problems = remote_migrate_problems(repo_state())
    if problems:
        print("refusing to migrate the shared dev database:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Applying migrations to the shared dev database (DATABASE_URL)...")
    return supabase(["migration", "up", "--db-url", url])


def test_int(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL_TEST", "")
    if url and not is_local_url(url):
        print("refusing: DATABASE_URL_TEST must point at local Supabase (127.0.0.1).")
        return 1
    code = reset_local()
    if code != 0:
        print("Local Supabase isn't running or failed to reset. Start it: `uv run poe db-up`.")
        return code
    return run_passthrough([sys.executable, "-m", "pytest", "-m", "integration", *argv])


def main(argv: list[str]) -> int:
    commands = {
        "up": up,
        "down": down,
        "migrate": lambda: migrate(argv[1:]),
        "test-int": lambda: test_int(argv[1:]),
    }
    if not argv or argv[0] not in commands:
        print(f"usage: python -m scripts.db {{{'|'.join(commands)}}} [options]")
        return 2
    return commands[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

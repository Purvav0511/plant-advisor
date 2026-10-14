"""Database tasks: `uv run poe db-up | db-down | migrate [--local] | test-int`.

- Local Supabase (Docker) is only for integration tests (PLAN 0.4). It starts just the
  services the tests need.
- `migrate` without `--local` applies migrations to the shared hosted dev project. It
  refuses if this branch is behind GitHub, so you never migrate from a stale checkout.
- `reset` only ever targets the local database. Nothing here can reset a remote one.
"""

from __future__ import annotations

import os
import sys
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


def is_local_url(url: str) -> bool:
    """Whether a Postgres URL points at this machine."""
    return (urlparse(url).hostname or "") in LOCAL_HOSTS


def supabase(args: list[str]) -> int:
    if find_tool("pnpm") is None:
        print("error: pnpm not found. Run `corepack enable` (DEV_SETUP §4).")
        return 127
    return run_passthrough(["pnpm", "exec", "supabase", *args])


def branch_is_behind() -> tuple[bool, str]:
    """Whether the current branch is behind its upstream on GitHub (after fetching)."""
    run_capture(["git", "fetch", "--quiet"], timeout=60)
    proc = run_capture(["git", "rev-list", "--count", "HEAD..@{upstream}"])
    if proc is None or proc.returncode != 0:
        return False, "no upstream branch to compare with"
    behind = int(proc.stdout.strip() or 0)
    return behind > 0, f"{behind} commit(s) behind GitHub"


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
    behind, detail = branch_is_behind()
    if behind:
        print(f"refusing: this branch is {detail}. Run `git pull` first.")
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
        "up": lambda: up(),
        "down": lambda: down(),
        "migrate": lambda: migrate(argv[1:]),
        "test-int": lambda: test_int(argv[1:]),
    }
    if not argv or argv[0] not in commands:
        print(f"usage: python -m scripts.db {{{'|'.join(commands)}}} [options]")
        return 2
    return commands[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

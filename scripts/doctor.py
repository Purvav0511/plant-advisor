"""`uv run poe doctor`: check this machine is ready to work on the repo.

Checks tool versions, env var *names* (never values) against .env.example, database
reachability and migration drift, CRLF files, and the repo's location.
Exit code 1 if any check fails; warnings don't fail.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import PurePath

from scripts._common import REPO_ROOT, find_tool, run_capture
from scripts.machine import describe

OK, WARN, FAIL = "ok", "warn", "FAIL"

# Folder names that indicate a synced folder (DEV_SETUP §1: never put the repo there).
SYNCED_MARKERS = (
    "onedrive",
    "dropbox",
    "icloud",
    "mobile documents",
    "cloudstorage",
    "google drive",
)


@dataclass(frozen=True)
class Result:
    status: str
    name: str
    detail: str


# --- pure helpers (unit-tested) ------------------------------------------------------


def parse_env_names(text: str) -> dict[str, bool]:
    """Map each variable name in a dotenv text to whether it has a non-empty value."""
    names: dict[str, bool] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        names[key] = value.strip().strip("'\"") != ""
    return names


def compare_env(example: dict[str, bool], actual: dict[str, bool]) -> tuple[list[str], list[str]]:
    """Return (names missing from .env, names present but empty)."""
    missing = [n for n in example if n not in actual]
    empty = [n for n in example if n in actual and not actual[n]]
    return missing, empty


def crlf_files(ls_files_eol: str) -> list[str]:
    """Files whose index copy has CRLF endings, from `git ls-files --eol` output."""
    bad: list[str] = []
    for line in ls_files_eol.splitlines():
        fields, _, path = line.partition("\t")
        index_eol = fields.split()[0] if fields.split() else ""
        if index_eol in ("i/crlf", "i/mixed"):
            bad.append(path)
    return bad


def location_problems(path: PurePath, *, is_wsl: bool) -> list[str]:
    """Reasons the repo location is unsafe (synced folder, or the Windows drive from WSL)."""
    problems: list[str] = []
    lowered = [p.lower() for p in path.parts]
    if is_wsl and len(lowered) > 2 and lowered[1] == "mnt" and len(lowered[2]) == 1:
        problems.append("the repo is on the Windows drive (/mnt/...); clone it into ~/code")
    for marker in SYNCED_MARKERS:
        if any(marker in part for part in lowered):
            problems.append(f"the repo is inside a synced folder ({marker}); move it to ~/code")
            break
    return problems


def migration_drift(local: list[str], applied: list[str]) -> tuple[list[str], list[str]]:
    """Return (local migrations not applied, applied migrations unknown to this checkout)."""
    return sorted(set(local) - set(applied)), sorted(set(applied) - set(local))


def major_version(text: str) -> int | None:
    match = re.search(r"(\d+)\.\d+", text)
    return int(match.group(1)) if match else None


# --- checks ----------------------------------------------------------------------------


def check_python() -> Result:
    v = sys.version_info
    status = OK if (v.major, v.minor) == (3, 12) else FAIL
    return Result(status, "python", f"{v.major}.{v.minor}.{v.micro} (need 3.12)")


def check_tool(name: str, args: list[str], *, required: bool = True) -> Result:
    proc = run_capture([name, *args])
    if proc is None or proc.returncode != 0:
        return Result(FAIL if required else WARN, name, "not found on PATH")
    first = (proc.stdout or proc.stderr).strip().splitlines()[:1]
    return Result(OK, name, first[0] if first else "found")


def check_node() -> Result:
    proc = run_capture(["node", "--version"])
    if proc is None:
        return Result(FAIL, "node", "not found on PATH")
    version = proc.stdout.strip()
    status = OK if major_version(version) == 22 else FAIL
    return Result(status, "node", f"{version} (need 22)")


def check_pnpm() -> Result:
    pinned = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["packageManager"]
    want = pinned.split("@", 1)[1]
    proc = run_capture(["pnpm", "--version"])
    if proc is None:
        return Result(FAIL, "pnpm", "not found; run `corepack enable`")
    have = proc.stdout.strip()
    status = OK if have == want else WARN
    return Result(status, "pnpm", f"{have} (package.json pins {want})")


def check_docker() -> list[Result]:
    if find_tool("docker") is None:
        return [Result(WARN, "docker", "not found; needed for `poe test-int` (DEV_SETUP §4)")]
    proc = run_capture(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
    if proc is None or proc.returncode != 0:
        return [Result(WARN, "docker", "CLI found but the daemon isn't running; start Docker")]
    return [Result(OK, "docker", f"server {proc.stdout.strip()}")]


def check_env() -> list[Result]:
    example_path, env_path = REPO_ROOT / ".env.example", REPO_ROOT / ".env"
    if not env_path.exists():
        return [Result(FAIL, ".env", "missing; copy .env.example to .env and fill in values")]
    example = parse_env_names(example_path.read_text(encoding="utf-8"))
    actual = parse_env_names(env_path.read_text(encoding="utf-8"))
    missing, empty = compare_env(example, actual)
    results = [
        Result(FAIL, ".env", f"missing names: {', '.join(missing)}")
        if missing
        else Result(OK, ".env", f"all {len(example)} names from .env.example present")
    ]
    if empty:
        results.append(
            Result(WARN, ".env", f"{len(empty)} empty (fill in when needed): {', '.join(empty)}")
        )
    return results


def local_migrations() -> list[str]:
    folder = REPO_ROOT / "supabase" / "migrations"
    if not folder.is_dir():
        return []
    return sorted(p.name.split("_", 1)[0] for p in folder.glob("*.sql"))


def check_database() -> list[Result]:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return [Result(WARN, "database", "DATABASE_URL is empty; skipped (PLAN 0.5)")]
    try:
        import psycopg
    except ImportError:
        return [Result(FAIL, "database", "psycopg isn't installed; run `uv sync`")]
    try:
        with psycopg.connect(url, connect_timeout=8) as conn:
            conn.execute("select 1")
            row = conn.execute(
                "select to_regclass('supabase_migrations.schema_migrations') is not null"
            ).fetchone()
            applied: list[str] = []
            if row and row[0]:
                rows = conn.execute("select version from supabase_migrations.schema_migrations")
                applied = [str(r[0]) for r in rows.fetchall()]
    except psycopg.Error as exc:
        timed_out = "timeout" in str(exc).lower()
        hint = " (use the Session pooler URL, DEV_SETUP §5)" if timed_out else ""
        return [Result(FAIL, "database", f"can't connect{hint}: {type(exc).__name__}")]
    results = [Result(OK, "database", "reachable")]
    not_applied, unknown = migration_drift(local_migrations(), applied)
    if not_applied:
        results.append(
            Result(WARN, "migrations", f"not applied yet: {', '.join(not_applied)} (poe migrate)")
        )
    if unknown:
        results.append(
            Result(FAIL, "migrations", f"applied but not in this checkout: {', '.join(unknown)}")
        )
    if not not_applied and not unknown:
        results.append(Result(OK, "migrations", "no drift"))
    return results


def check_line_endings() -> Result:
    proc = run_capture(["git", "ls-files", "--eol"])
    if proc is None or proc.returncode != 0:
        return Result(WARN, "line endings", "couldn't run `git ls-files --eol`")
    bad = crlf_files(proc.stdout)
    if bad:
        return Result(FAIL, "line endings", f"CRLF in: {', '.join(bad[:10])}")
    return Result(OK, "line endings", "no CRLF text files")


def check_location() -> Result:
    is_wsl = platform.system() == "Linux" and "microsoft" in platform.release().lower()
    problems = location_problems(REPO_ROOT, is_wsl=is_wsl)
    if problems:
        return Result(FAIL, "location", "; ".join(problems))
    return Result(OK, "location", str(REPO_ROOT))


def check_pre_commit() -> Result:
    hook = REPO_ROOT / ".git" / "hooks" / "pre-commit"
    if hook.exists():
        return Result(OK, "pre-commit", "hook installed")
    return Result(WARN, "pre-commit", "hook not installed; run `uv run pre-commit install`")


def main() -> int:
    print(f"machine: {describe()}\n")
    results: list[Result] = [
        check_python(),
        check_tool("uv", ["--version"]),
        check_node(),
        check_pnpm(),
        check_tool("git", ["--version"]),
        *check_docker(),
        *check_env(),
        *check_database(),
        check_line_endings(),
        check_location(),
        check_pre_commit(),
    ]
    width = max(len(r.name) for r in results)
    for r in results:
        print(f"[{r.status:>4}] {r.name.ljust(width)}  {r.detail}")
    failed = [r for r in results if r.status == FAIL]
    warned = [r for r in results if r.status == WARN]
    print(f"\n{len(failed)} failed, {len(warned)} warnings")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

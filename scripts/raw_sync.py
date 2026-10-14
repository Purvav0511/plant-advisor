"""`uv run poe raw-push` / `raw-pull`: sync private files between machines through R2 (PLAN 0.5).

Client documents, private eval photos and ingestion reports never enter git (CLAUDE.md
invariant 12). They travel through a private prefix in the R2 dev bucket instead.

Safety rules:
- Files are compared by SHA-256 checksum. Identical files are skipped.
- A file that differs on the two sides is a **conflict**: it's reported and skipped, unless
  `--overwrite`. Raw documents are never edited, so a difference needs a human decision.
- Push deletes remote files only with `--prune`. Pull never deletes local files.
- `--dry-run` shows the plan and changes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol

from scripts._common import REPO_ROOT

# Repo-relative folders that sync (all gitignored).
SYNCED_FOLDERS = ("data/raw", "evals/photos/private", "ingestion/reports")


class Store(Protocol):
    """Where synced files live remotely. `scripts.r2.R2Store` in real use; a fake in tests."""

    def list(self, prefix: str) -> dict[str, str]:
        """Every key under `prefix`, mapped to its SHA-256."""
        ...

    def upload(self, path: Path, key: str, sha256: str) -> None: ...

    def download(self, key: str, path: Path) -> None: ...

    def delete(self, key: str) -> None: ...


@dataclass
class Plan:
    """What a sync would do, by repo-relative path."""

    copy: list[str] = field(default_factory=list)
    same: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)
    target_only: list[str] = field(default_factory=list)


def plan(source: dict[str, str], target: dict[str, str], *, overwrite: bool, prune: bool) -> Plan:
    """Compare checksums by path. `source` is copied onto `target`."""
    result = Plan()
    for path in sorted(source):
        if path not in target:
            result.copy.append(path)
        elif source[path] == target[path]:
            result.same.append(path)
        elif overwrite:
            result.copy.append(path)
        else:
            result.conflicts.append(path)
    result.target_only = sorted(set(target) - set(source))
    if prune:
        result.delete = list(result.target_only)
    return result


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_local(root: Path) -> dict[str, str]:
    """Every file in the synced folders under `root`, mapped to its SHA-256."""
    files: dict[str, str] = {}
    for folder in SYNCED_FOLDERS:
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = sha256_of(path)
    return files


def safe_relative(path: str) -> bool:
    """Whether a remote path stays inside one of the synced folders (no `..`, not absolute)."""
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        return False
    return any(path.startswith(f"{folder}/") for folder in SYNCED_FOLDERS)


def run_sync(
    direction: str,
    root: Path,
    store: Store,
    *,
    prefix: str,
    overwrite: bool = False,
    prune: bool = False,
    dry_run: bool = False,
) -> int:
    """Push or pull. Returns 0 when everything synced, 1 when anything was skipped."""
    if direction not in ("push", "pull"):
        raise ValueError(f"unknown direction {direction!r}")
    local = scan_local(root)
    remote: dict[str, str] = {}
    unsafe: list[str] = []
    for key, digest in store.list(prefix).items():
        rel = key.removeprefix(prefix)
        if safe_relative(rel):
            remote[rel] = digest
        else:
            unsafe.append(key)

    if direction == "push":
        p = plan(local, remote, overwrite=overwrite, prune=prune)
    else:
        # Pull never deletes local files, whatever the flags say.
        p = plan(remote, local, overwrite=overwrite, prune=False)

    verb = "upload" if direction == "push" else "download"
    print(f"{direction}: {len(p.copy)} to {verb}, {len(p.same)} already identical", end="")
    print(
        f", {len(p.conflicts)} conflict(s), {len(p.delete)} to delete"
        + (" (dry run)" if dry_run else "")
    )
    for path in p.copy:
        print(f"  {verb}  {path}")
    for path in p.delete:
        print(f"  delete  {prefix}{path}")
    for path in p.conflicts:
        print(
            f"  CONFLICT  {path}: different on the two sides; skipped (use --overwrite to replace)"
        )
    for key in unsafe:
        print(f"  UNSAFE  {key}: outside the synced folders; skipped")
    if direction == "push" and p.target_only and not prune:
        print(f"  ({len(p.target_only)} remote-only file(s) kept; --prune would delete them)")

    if not dry_run:
        for path in p.copy:
            if direction == "push":
                store.upload(root / path, f"{prefix}{path}", local[path])
            else:
                store.download(f"{prefix}{path}", root / path)
        for path in p.delete:
            store.delete(f"{prefix}{path}")
    return 1 if p.conflicts or unsafe else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="raw_sync", description="Sync private files between machines through R2 (PLAN 0.5)"
    )
    parser.add_argument("direction", choices=["push", "pull"])
    parser.add_argument("--overwrite", action="store_true", help="replace files that differ")
    parser.add_argument("--prune", action="store_true", help="push only: delete remote-only files")
    parser.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    args = parser.parse_args(argv)

    from scripts.r2 import R2Store, raw_prefix  # needs boto3 and the R2 env vars

    return run_sync(
        args.direction,
        REPO_ROOT,
        R2Store.from_env(),
        prefix=raw_prefix(),
        overwrite=args.overwrite,
        prune=args.prune,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

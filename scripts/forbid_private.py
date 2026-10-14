"""Pre-commit hook: refuse to commit client data or secrets (CLAUDE.md invariants 9 and 12).

`.gitignore` already excludes these paths; this catches `git add -f` and renamed copies.
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

FORBIDDEN_PREFIXES = ("data/raw/", "evals/photos/private/", "ingestion/reports/")
FORBIDDEN_SUFFIXES = (".pem", ".key")


def is_forbidden(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/"))
    posix = p.as_posix()
    if posix.startswith(FORBIDDEN_PREFIXES):
        return True
    if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
        return True
    return p.suffix in FORBIDDEN_SUFFIXES


def main(paths: list[str]) -> int:
    bad = [p for p in paths if is_forbidden(p)]
    for p in bad:
        print(f"refusing to commit {p}: client data or secrets never go into git")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

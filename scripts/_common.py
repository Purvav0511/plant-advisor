"""Shared helpers for the scripts behind `uv run poe <task>`.

Everything here must work unchanged on macOS, Linux and Windows (CLAUDE.md invariant 15).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_tool(name: str) -> str | None:
    """Full path of an executable on PATH (handles .cmd/.exe shims on Windows)."""
    return shutil.which(name)


def run_capture(args: list[str], timeout: float = 30) -> subprocess.CompletedProcess[str] | None:
    """Run a command and capture its output. Returns None if the tool is missing or times out."""
    exe = find_tool(args[0])
    if exe is None:
        return None
    try:
        return subprocess.run(
            [exe, *args[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_passthrough(args: list[str]) -> int:
    """Run a command with inherited stdio and return its exit code."""
    exe = find_tool(args[0])
    if exe is None:
        print(f"error: `{args[0]}` not found on PATH")
        return 127
    try:
        return subprocess.run([exe, *args[1:]], check=False, cwd=REPO_ROOT).returncode
    except KeyboardInterrupt:
        return 130

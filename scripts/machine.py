"""Print the machine label and OS, for docs/PROGRESS.md entries."""

from __future__ import annotations

import os
import platform


def describe() -> str:
    label = os.environ.get("DEV_MACHINE") or "(DEV_MACHINE not set)"
    system = platform.system()
    release = platform.release()
    if system == "Linux" and "microsoft" in release.lower():
        system = "Linux (WSL2)"
    return f"{label} · {system} {release} · {platform.machine()}"


if __name__ == "__main__":
    print(describe())

"""Run api, worker and web together with prefixed output: `uv run poe dev`.

Ctrl+C stops all of them. If one exits, the others are stopped too.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import IO

from scripts._common import REPO_ROOT, find_tool
from scripts.serve import command as service_command

COLORS = {"api": "\033[36m", "worker": "\033[35m", "web": "\033[32m"}
RESET = "\033[0m"


def commands() -> dict[str, list[str]]:
    pnpm = find_tool("pnpm")
    if pnpm is None:
        raise SystemExit("error: pnpm not found. Run `corepack enable` (DEV_SETUP §4).")
    return {
        "api": service_command("api"),
        "worker": service_command("worker"),
        "web": [pnpm, "--filter", "@advisor/web", "dev"],
    }


def pump(name: str, stream: IO[str], width: int) -> None:
    prefix = f"{COLORS.get(name, '')}{name.ljust(width)} |{RESET} "
    for line in stream:
        sys.stdout.write(prefix + line)
        sys.stdout.flush()


def main() -> int:
    cmds = commands()
    width = max(len(n) for n in cmds)
    procs: dict[str, subprocess.Popen[str]] = {}
    threads: list[threading.Thread] = []
    for name, cmd in cmds.items():
        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        procs[name] = proc
        assert proc.stdout is not None
        t = threading.Thread(target=pump, args=(name, proc.stdout, width), daemon=True)
        t.start()
        threads.append(t)

    exit_code = 0
    try:
        while all(p.poll() is None for p in procs.values()):
            threading.Event().wait(0.5)
        for name, p in procs.items():
            if p.returncode is not None:
                print(f"{name} exited with code {p.returncode}; stopping the others.")
                exit_code = p.returncode or 1
                break
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""Run one backend service: `python -m scripts.serve api|worker|mcp`."""

from __future__ import annotations

import os
import subprocess
import sys

from scripts._common import REPO_ROOT

# service -> (port env var, default port, how to start it)
SERVICES: dict[str, tuple[str, int, list[str]]] = {
    "api": ("API_PORT", 8000, ["uvicorn", "advisor_api.main:app"]),
    "worker": ("WORKER_PORT", 8001, ["uvicorn", "advisor_worker.main:app"]),
    "mcp": ("MCP_PORT", 8002, ["advisor_mcp"]),
}

RELOAD_DIRS = ["packages/core/src", "services"]


def command(service: str) -> list[str]:
    port_var, default_port, target = SERVICES[service]
    port = os.environ.get(port_var) or str(default_port)
    if target[0] == "uvicorn":
        reload_args = [arg for d in RELOAD_DIRS for arg in ("--reload-dir", str(REPO_ROOT / d))]
        return [
            sys.executable, "-m", "uvicorn", target[1],
            "--host", "127.0.0.1", "--port", port, "--reload", *reload_args,
        ]  # fmt: skip
    return [sys.executable, "-m", target[0], "--port", port]


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in SERVICES:
        print(f"usage: python -m scripts.serve {{{'|'.join(SERVICES)}}}")
        return 2
    try:
        return subprocess.run(command(argv[0]), check=False, cwd=REPO_ROOT).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

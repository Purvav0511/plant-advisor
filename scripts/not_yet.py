"""Placeholder for poe tasks whose PLAN task hasn't been built yet."""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    task, plan_id = argv[0], argv[1]
    print(f"`uv run poe {task}` isn't implemented yet. It arrives with PLAN task {plan_id}.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

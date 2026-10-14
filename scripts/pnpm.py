"""Run pnpm with the given arguments: `python -m scripts.pnpm --filter @advisor/web lint`.

Poe runs commands without a shell, and on Windows pnpm is a `.cmd` shim that only
`shutil.which` finds, so Node tasks go through this wrapper.
"""

from __future__ import annotations

import sys

from scripts._common import find_tool, run_passthrough


def main(argv: list[str]) -> int:
    if find_tool("pnpm") is None:
        print("error: pnpm not found. Run `corepack enable` (DEV_SETUP §4).")
        return 127
    return run_passthrough(["pnpm", *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

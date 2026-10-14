# 0018: Python workspace layout and package names

**Context:** CLAUDE.md and SPEC name files like `packages/core/playbooks/loader.py`. A uv workspace needs each member to be an installable package with an import name that doesn't collide with anything on PyPI (`core` would).

**Decision**
- Each member uses the `src` layout with an `advisor_*` import name: `packages/core/src/advisor_core/`, `services/api/src/advisor_api/`, `services/worker/src/advisor_worker/`, `services/mcp/src/advisor_mcp/`, `ingestion/src/advisor_ingestion/`, `evals/src/advisor_evals/`. Tests live in each member's `tests/`.
- Paths in SPEC, PLAN and CLAUDE.md map directly: `packages/core/playbooks/loader.py` means `packages/core/src/advisor_core/playbooks/loader.py`.
- The repo root is a non-package uv project that depends on every member, so one `uv sync` installs everything; dev tools are in its `dev` group.
- Node tools run through `scripts/pnpm.py`, because poe runs commands without a shell and pnpm is a `.cmd` shim on Windows.
- `poe` tasks whose PLAN task isn't built yet exist and exit with "arrives with PLAN task X" (`scripts/not_yet.py`).

**Alternatives:** flat `packages/core/core/` (ambiguous imports); a virtual workspace root (`uv sync` wouldn't install all members by default).

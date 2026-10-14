# Progress

This file is the shared memory between your machines and between sessions. Claude Code's local chat history stays on the machine where it ran, so anything the next session needs goes here.

- `/handoff` updates this file at the end of every session.
- `/pickup` reads it at the start of the next one.
- The newest log entry goes first. Keep entries short and factual, and never put secret values here.

## Current state

- **Branch:** `task/0.5-shared-dev` (PR into `dev`, closes #9)
- **PLAN task:** 0.5 Shared dev environment (in review). Done here: migration applied to the shared dev DB (doctor: no drift); `raw-push`/`raw-pull` built and tested through the real bucket; CORS rules written and checker built. **Waiting on the owner:** paste the CORS rules in the dashboard, then `uv run poe r2-cors` should pass. The cross-machine "Done when" is completed with the Mac at 0.6.
- **Branch model:** `dev` = integration and default branch; `main` = production (decision 0019). Branch from `dev`.
- **Board:** https://github.com/users/Purvav0511/projects/3 (Cycle 1 left: 0.1, 0.5 in review, 0.6).
- **Next step:** owner reads, tests and merges this PR; then PLAN 0.6 (Mac setup), or Phase 1 (1.1 core schema) on this PC.
- **Blockers / waiting on (from the client):** wear scale, composition values, carbon range, product description (issues #70–#73). The 11 data sheets aren't in `data/raw/wear_protection/` yet; put them there and `uv run poe raw-push` when available (needed by 1.7).
- **On the other machine (Mac):** not set up yet. `.env` from the password manager, including the two new secrets.

## Log

### 2026-10-14 · pc-wsl · 0.5
- **Changed:** the shared dev database got migration `20261014020917` (vector 0.8.2, pgmq 1.5.1, same as local); `WORKER_DRAIN_SECRET` and `MCP_SERVICE_TOKEN` generated into `.env` (never printed).
- **Changed:** `scripts/raw_sync.py` (`poe raw-push` / `raw-pull`: checksums, conflicts skipped unless `--overwrite`, remote deletes only with `--prune`, `--dry-run`, unsafe keys refused) and `scripts/r2.py` (R2 store with verified downloads; `poe r2-cors` checks CORS by browser-style preflight); `config/r2-cors.json`.
- **Changed:** `[tool.uv] exclude-newer = "14 days"` (Python follows decision 0020; 31 packages stepped back a release; all checks pass); `boto3` added to the dev tools.
- **Verified for real:** push, identical re-push skipped, pull into an empty folder byte-identical, a real conflict refused; test file removed from R2 afterwards.
- **Decisions:** [0021](decisions/0021-r2-least-privilege-and-raw-sync.md) R2 least privilege, CORS and raw sync; 0020 extended to Python.
- **Next:** owner pastes CORS rules (`uv run poe r2-cors --rules`), then `uv run poe r2-cors` passes.
- **On the other machine:** `git pull`, `uv sync` (Python lock changed), `pnpm install`; copy `WORKER_DRAIN_SECRET` and `MCP_SERVICE_TOKEN` from the password manager into `.env`; then `uv run poe raw-pull` and compare with this PC (0.6).

### 2026-10-14 · pc-wsl · maintenance (#77)
- **Changed:** `.github/dependabot.yml` (14-day cooldown, no automatic majors, `@types/node` < 23, Docker Python < 3.13); `pnpm-workspace.yaml` `minimumReleaseAge: 20160`; `apps/web` `@types/node` ^20 → ^22; `pnpm-lock.yaml` re-resolved under the rule.
- **Also (0.4 follow-up, merged in #76):** remote `poe migrate` runs only from a clean `dev` level with GitHub; found during the owner's walkthrough.
- **Decisions:** [0020](decisions/0020-dependency-update-policy.md) dependency update policy.
- **Next:** PLAN 0.5.
- **On the other machine:** `git pull`, then `pnpm install` (the lockfile changed).

### 2026-10-14 · pc-wsl · 0.4
- **Changed:** `supabase/` (`supabase init`; seeding off until 1.4) and the first migration enabling `vector` and `pgmq`.
- **Changed:** `scripts/db.py` behind `poe db-up` (starts only Postgres, auth and the gateway), `db-down`, `migrate [--local]` (remote refuses if the branch is behind GitHub), `test-int` (resets the **local** DB only, then runs tests marked `integration`).
- **Changed:** integration tests in `packages/core/tests/integration/` (migrations match the repo, pgvector distance, pgmq round trip). CI's integration job now switches on.
- **Also:** board created (GitHub Project 3) with Status, Cycle, and Backlog/Board/Roadmap views; handbook links it.
- **Next:** PLAN 0.5 after the owner's accounts exist.
- **On the other machine:** Docker must be running for `poe db-up`; first start downloads the Supabase images (a few minutes).

### 2026-10-13 · pc-wsl · 0.3
- **Changed:** `dev` branch created and made the default; branch model and free stand-ins for branch protection: `scripts/branch_rules.py`, `guard_branch.py` (pre-commit and pre-push hooks), `merge.py` (`poe merge`), `verify_push.py` (`guard` workflow).
- **Changed:** workflows `ci.yml`, `guard.yml`, `cross-os.yml`, `security.yml`, the shared setup action, Dependabot; actions pinned by SHA. `docker/service.Dockerfile` builds api, worker and mcp (tagged by tree hash, smoke-tested).
- **Fixed:** torchvision now comes from the PyTorch CPU index too; before, `import open_clip` failed with mismatched builds. The doctor and CI now check the embedding libraries import.
- **Decisions:** [0019](decisions/0019-branches-environments-cicd.md) branches, environments and CI/CD.
- **Changed (same PR, second commit):** `docs/handbook/` (plain-language guide: product, stack, decisions with pros and cons, how we ship, working with AI, the board, glossary); reading-before-merge practice (`.github/pull_request_template.md`, `/walkthrough` skill, `poe merge` requires the owner's "I read every changed file" tick); the board: 8 epics, 58 stories and 4 client items as GitHub issues (#4–#73), story 0.2 closed.
- **Next:** owner reads PR #3 (`/walkthrough 3`), ticks the box, merges with `uv run poe merge 3`; check the `guard` run; create the GitHub Project once the owner grants the `project` scope; then PLAN 0.4.
- **On the other machine:** `uv sync` (torchvision changed), then `uv run pre-commit install` to add the pre-push hook. Branch from `dev` from now on.

### 2026-10-13 · pc-wsl · 0.2
- **Changed:** uv workspace (`packages/core`, `services/api|worker|mcp`, `ingestion`, `evals`; `src` layout, `advisor_*` names) with a universal `uv.lock` (PyTorch CPU index on Linux and Windows, PyPI on macOS); pnpm workspace with `apps/web` (Next.js 16.3.8, static export, Tailwind) and the root `package.json` (Supabase CLI 2.118.0, Playwright 1.63.0).
- **Changed:** every poe task from CLAUDE.md in the root `pyproject.toml` (later tasks print which PLAN task brings them); `scripts/` doctor, machine, serve, dev, pnpm wrapper, private-file guard, with unit tests.
- **Changed:** ruff (pathlib, encoding and no-`shell=True` rules), pyright (strict in core), eslint, tsc (after `next typegen`), prettier; pre-commit hooks; minimal `/health` API and worker, an MCP v2 server with no tools yet.
- **Decisions:** [0018](decisions/0018-python-package-layout.md) package layout. The MCP SDK is v2 (`MCPServer`, not `FastMCP`).
- **Next:** PLAN 0.3 (CI).
- **On the other machine:** after cloning, `uv sync`, `pnpm install`, `cp .env.example .env` (set `DEV_MACHINE=mac`), `uv run pre-commit install`, then `uv run poe doctor` and `uv run poe check`.

### 2026-10-13 · pc-wsl · 0.1
- **Changed:** created the private repo `Purvav0511/plant-advisor` from the handoff package; added decision notes 0002–0017; updated SPEC (v3), PLAN, CLAUDE.md (invariants 13 and 14 added, cross-platform is now 15), DEV_SETUP, `.env.example` (email vars); pinned `@playwright/mcp`; added `.nvmrc`.
- **Decisions** (design session with the owner; reasoning in each note):
  - Recommendations come from scored diagnosis plus catalog rules, not vector search; naive RAG is only the baseline ([0002](decisions/0002-recommendations-from-rules-not-rag.md)). Products get a stable `code` ([0003](decisions/0003-product-codes.md)).
  - Plant staff join by invite link or plant code; history is server-side and shared per plant ([0004](decisions/0004-plant-onboarding-and-history.md)).
  - The plant user sees the recommendation as preliminary, withheld when confidence is low or checks fail, with call / text / message actions ([0005](decisions/0005-plant-sees-preliminary-recommendation.md)).
  - Separate `engineer` and `sales` roles; one person can hold both ([0006](decisions/0006-engineer-and-sales-roles.md)).
  - Interactive ticket chat with layered guardrails; learning only through reviews and approved proposals ([0007](decisions/0007-ticket-chat-guardrails-learning.md)).
  - Photo check is a pipeline step ([0008](decisions/0008-photo-quality-gate.md)); Cloud Run now with a portable path to AWS, decided at 7.3 with measured numbers ([0009](decisions/0009-worker-trigger-and-hosting.md)).
  - Case embeddings in the worker (0010); own eval photos committed under `assets/eval-photos/` (0011); API runs under RLS (0012); transitions and attempts (0013); query-string routes (0014); Anthropic API first (0015); Figma first (0016); chat context lives in the repo (0017).
- **Next:** merge the PR, then PLAN 0.2.
- **On the other machine:** set up the Mac per DEV_SETUP §4a (uv, fnm or nvm with the latest Node 22, pnpm via corepack, Docker Desktop, gh, Claude Code, cloudflared, LibreOffice), clone into `~/code/plant-advisor`, then `/pickup`.
- **PC tool state:** uv 0.13.0, Node 22.23.3 (nvm), pnpm 12.11.2, cloudflared, gh, Claude Code, Docker 27.2 (WSL integration on). LibreOffice is not installed yet (needs sudo; only for PLAN 1.7).

### 2026-10-12 · setup · 0.0
- **Changed:** repository created from the handoff package: CLAUDE.md, SPEC, PLAN, DEV_SETUP, the wear playbook, and the `.claude/` settings and skills.
- **Decisions:** `docs/decisions/0001-cross-platform-dev.md`.
- **Next:** PLAN 0.1.
- **On the other machine:** nothing yet.

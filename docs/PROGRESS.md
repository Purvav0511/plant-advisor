# Progress

This file is the shared memory between your machines and between sessions. Claude Code's local chat history stays on the machine where it ran, so anything the next session needs goes here.

- `/handoff` updates this file at the end of every session.
- `/pickup` reads it at the start of the next one.
- The newest log entry goes first. Keep entries short and factual, and never put secret values here.

## Current state

- **Branch:** `task/0.1-design-decisions` (PR open against `main`)
- **PLAN task:** 0.1 Accounts and secrets (in progress). Design decisions done; accounts not created yet.
- **Next step:** merge the design-decisions PR, then start PLAN 0.2 (repository skeleton and task runner) on `task/0.2-skeleton`. Accounts can be created as each one is needed (PLAN 0.1 lists when).
- **Blockers / waiting on (from the client):**
  - the five-level wear scale for 9 products
  - missing composition values
  - the corrected carbon range for one wire
  - the missing product description (SPEC §18)
- **Last check:** not run yet (no `poe` tasks until 0.2)
- **On the other machine (Mac):** clone `https://github.com/Purvav0511/plant-advisor` into `~/code/plant-advisor`, install the tools per `docs/DEV_SETUP.md` §4a, then `/pickup`.

## Log

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

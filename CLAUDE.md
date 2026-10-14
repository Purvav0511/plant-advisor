# CLAUDE.md: Plant Advisor

A plant technician photographs a worn or failed component and answers a few questions. An AI worker diagnoses the problem through a **product-family playbook** and drafts a grounded recommendation. An engineer reviews **every** request before a quote goes out.

- Full spec: `docs/SPEC.md`. Build plan: `docs/PLAN.md`.
- Machine setup and testing: `docs/DEV_SETUP.md`. Session state: `docs/PROGRESS.md`.
- Work on **one PLAN.md task at a time**, in order, unless told otherwise.

## Sessions across machines

Development happens on a **Mac** and a **Windows PC (inside WSL2 Ubuntu)**, and sometimes in cloud sessions. Local session history does **not** move between machines; the repo does.

- **Start** every session with `/pickup`. It syncs, refreshes dependencies, runs the doctor and the checks, and reads `docs/PROGRESS.md`.
- **End** every session with `/handoff`. It runs the checks, updates `docs/PROGRESS.md`, commits to the task branch and pushes.
- Anything the next session needs goes in `docs/PROGRESS.md` or `docs/decisions/`, not in chat. That includes manual steps for the other machine: new env var *names*, new tools, migrations, raw files to pull.
- Use one branch per PLAN task (`task/<id>-<slug>`). Never commit straight to `main`, and never force-push.

## Stack

- **Python 3.12** (`.python-version`), managed with **uv** (one universal `uv.lock`). Lint and format with **ruff**; types with **pyright** (strict in `packages/core`).
- **Task runner:** **poethepoet**, defined in the root `pyproject.toml` and run as `uv run poe <task>`. It runs the same on macOS, Linux and Windows. Tasks load `.env` automatically.
- **Node 22** (`.node-version`) with **pnpm**, pinned through `packageManager` in the root `package.json`. The Supabase CLI is a dev dependency (`pnpm exec supabase …`), so both machines run the same version.
- **Backend:** FastAPI (`services/api`), worker (`services/worker`), MCP server (`services/mcp`, Python MCP SDK). Shared library: `packages/core`. Docker images for Cloud Run are built in CI for `linux/amd64`.
- **Database:** Supabase Postgres with **pgvector** (embeddings) and **pgmq** (queue). Migrations live in `supabase/migrations` (Supabase CLI). Access from Python with psycopg 3 (`psycopg[binary]`). Daily development uses the shared hosted **dev** project. Integration tests use a **local** Supabase in Docker.
- **Storage:** Cloudflare R2 through its S3-compatible API (boto3). The browser uploads directly with presigned URLs.
- **Models:** all calls go through `packages/core/models/gateway.py`. Model IDs and prompt versions live in `config/models.yaml` and `prompts/`. `MODEL_PROVIDER=replay` serves recorded responses.
- **Embeddings:** an open-source image model (open_clip, ViT-B-32, 512-dim) and a small text model (sentence-transformers, 384-dim), both running in the worker on CPU. Use uv's PyTorch CPU index on Linux and Windows; macOS uses PyPI wheels.
- **PDF:** **ReportLab** for quotes. **pdfplumber** and **pypdfium2** for ingestion. LibreOffice (found via `SOFFICE_PATH` or `PATH`) only to convert `.doc` files.
- **Frontend:** Next.js (App Router, TypeScript), Tailwind and shadcn/ui, built as a static export. One app with `/plant` (phone-first PWA) and `/console` (desktop). Supabase JS handles auth and realtime; TanStack Query handles API calls.
- **Tests:** pytest (plus Hypothesis where useful), with recorded model responses. **Playwright** runs e2e on Chromium and WebKit with phone viewports. The eval harness lives in `evals/`.
- **Tracing and errors:** Langfuse for model and tool calls, Sentry for app errors.

## Layout

```
apps/web/                 Next.js app: /plant and /console route groups
services/api/             FastAPI: requests, uploads, reviews, quotes, knowledge approval
services/worker/          queue consumer: runs the 7-stage pipeline (drain endpoint + loop mode)
services/mcp/             read-only MCP tool server for agents (tenant-scoped)
packages/core/            shared Python: models (Pydantic), pipeline stages, playbook loader,
                          rule evaluator, gateway, embeddings, db access
playbooks/<id>/           playbook.yaml (vocabulary, questions, family schema, scoring, rules, checks)
prompts/                  versioned prompt templates (e.g. evidence.v1.md)
config/                   models.yaml, thresholds.yaml
supabase/                 config.toml, migrations/, seed/ (demo tenants, plants, components)
ingestion/                data-sheet ingestion: parsers, extraction prompts, validators
evals/                    test cases, baseline (naive RAG), harness, recordings/, reports/
scripts/                  cross-platform Python helpers behind poe tasks (doctor, dev, phone, raw sync)
data/raw/                 client source documents. GITIGNORED: never commit (synced via R2)
docs/                     SPEC.md, PLAN.md, DEV_SETUP.md, PROGRESS.md, decisions/
.claude/                  settings.json, skills/ (handoff, pickup). Committed
```

## Commands (create these in PLAN task 0.2)

All commands are `uv run poe <task>`, and they behave the same on the Mac, in WSL and on native Windows.

- **`doctor`:** checks tool versions, env var *names* against `.env.example`, database reachability, migration drift and line endings. Prints the machine label.
- **`machine`:** prints `DEV_MACHINE` and the OS. Used in `PROGRESS.md` entries.
- **`check`:** `lint` then `test`. Run it before every commit.
- **`lint`:** ruff, pyright, eslint and prettier in check mode.
- **`test`:** unit tests (fast, no network).
- **`test-int`:** integration tests against local Supabase. It resets that database, never the shared dev one.
- **`db-up` / `db-down`:** start or stop local Supabase in Docker.
- **`migrate`:** apply migrations to the shared dev database (`--local` targets local Supabase).
- **`seed`:** load demo data.
- **`api` / `worker` / `mcp` / `web`:** run one service, on ports 8000, 8001, 8002 and 3000.
- **`dev`:** run api, worker and web together. A Python script spawns them and prefixes their output.
- **`ingest --family wear_protection`:** run ingestion on `data/raw/wear_protection/`.
- **`eval`:** run the pipeline and the naive baseline on the eval set. It uses recorded responses; `--live` calls real models.
- **`eval-report`:** write `evals/reports/<date>.md`.
- **`e2e`:** Playwright end-to-end tests against the local stack with `MODEL_PROVIDER=replay`.
- **`phone`:** HTTPS tunnels (cloudflared) to the web app and the API for testing on a real phone.
- **`raw-pull` / `raw-push`:** sync `data/raw/`, `evals/photos/private/` and `ingestion/reports/` with the private R2 prefix.

## Invariants: never break these

1. **The model never chooses a product outside the candidate list.** Stage 4 passes candidate IDs, and code rejects any other ID. No free-text product names in outputs.
2. **Only approved knowledge is used live.** The pipeline reads only rows with `status = 'approved'` (products, rules, vocabulary, playbooks) and only cases created from engineer reviews. Drafts are never used.
3. **Request status changes only along the allowed-transitions table** in SPEC §6, and only through the DB function `transition_request(request_id, to_status, actor)`, which also writes an `events` row. Never update `requests.status` directly.
4. **Every pipeline stage is idempotent and checkpointed.** The unique key is `(request_id, attempt, stage)` in `pipeline_runs`. A retry resumes from the last successful stage. Running anything twice must never create a second analysis.
5. **All model calls go through the gateway** at temperature 0, with pinned model IDs and versioned prompts. Record `{model, prompt_version, catalog_version, playbook_version}` in `analyses.versions`.
6. **Tenant isolation:** every query filters by `tenant_id`, RLS is enabled on every table, and MCP tools are scoped to the caller's tenant.
7. **Core code never hardcodes a product family.** Family-specific vocabulary, questions, scoring, rules and checks live in `playbooks/<id>/`. Code reads them through the playbook loader.
8. **No client data goes to free-tier model APIs.** Only paid endpoints are configured for real data. Free tiers may be used with synthetic data only.
9. **No secrets in code.** Read them from environment variables. `.env.example` lists names without values. Never read, print or commit `.env`.
10. **Never invent metrics.** Report accuracy, calibration, latency or cost in README or reports only after measuring it with `uv run poe eval`.
11. **All times are stored in UTC** (timestamptz) and converted in the UI.
12. **Raw client documents never enter git.** `data/raw/`, `evals/photos/private/` and `ingestion/reports/` are gitignored and sync through R2. Fixtures use synthetic or user-approved samples.
13. **Everything runs on macOS, Linux and Windows.** Follow `docs/DEV_SETUP.md` §8:
    - Paths and files: `pathlib`, `tempfile`, explicit `encoding="utf-8"`, LF endings, no case-only filename differences.
    - Processes: subprocess with argument lists and no `shell=True`; find external tools with `shutil.which` or an env var.
    - Tasks: poe tasks use `cmd`, `script` or `sequence`, never `shell`; helpers are Python under `scripts/`; options are flags, not inline env vars.
    - A change that only works on one OS isn't done.

## How to work

- Write tests first for the rule evaluator, the status transitions, the stage contracts, the checks and the scoring. Then implement until green.
- Keep changes scoped to the current PLAN task, and don't refactor unrelated code.
- Make small commits that start with the task ID, e.g. `3.4: diagnosis scoring`. Run `uv run poe check` first.
- For a real design decision, add a 5–10 line note in `docs/decisions/NNNN-title.md` covering context, decision, why and alternatives.
- If a test is flaky, fix the cause. Never add sleeps or blind retries.
- When stage output fails validation, retry once with the validation error included, then fail the stage and route the request to an engineer.
- When requirements are unclear, read SPEC first. If it's still unclear, ask before building.
- Never edit a migration that has been applied to the shared dev database. Add a new one.

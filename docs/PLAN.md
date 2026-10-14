# Plant Advisor: Implementation Plan

Work through the tasks in order. Each task has a **Done when** check, and the task isn't finished until that check passes. Commit messages start with the task ID. Read `CLAUDE.md` and `docs/SPEC.md` first.

**Every session** starts with `/pickup` and ends with `/handoff`, because work moves between the Mac and the PC (`docs/DEV_SETUP.md`). Use one branch per task (`task/<id>-<slug>`), merged through a PR when CI is green. Unless a task says otherwise, "passes" means it passes on whichever machine you're on, and CI covers the rest.

Legend: 🧪 write tests first · 👤 needs the human (accounts, approvals, photos)

---

## Phase 0: Setup

**0.1 👤 Accounts, secrets and the first machine**

Create the accounts (DEV_SETUP §3):
- GitHub private repository, with the Claude GitHub App if you'll use cloud sessions
- Supabase **dev** project
- Cloudflare account with an R2 **dev** bucket
- Google Cloud project with Cloud Run and Cloud Scheduler
- Langfuse
- Sentry
- A paid model API key
- A password manager note holding the `.env` values

Then:
- Set up the first machine per DEV_SETUP §4.
- Push this handoff package as the first commit. The provided `.gitignore` already protects `data/raw/`.
- Fill in `.env` from `.env.example`.

Done when: the first machine passes DEV_SETUP §4, and `uv run poe doctor` (after task 0.2) reports every variable present.

**0.2 Repository skeleton and the cross-platform task runner**
- Create the layout from CLAUDE.md:
  - a uv workspace (`packages/core`, `services/*`, `ingestion`, `evals`) with `[tool.uv]` and the PyTorch CPU index for Linux and Windows only (uv's PyTorch guide)
  - a pnpm workspace for `apps/web`
  - a root `package.json` with `packageManager` (pnpm) and `supabase` and `@playwright/test` as dev dependencies
- Add **poethepoet** with every task from CLAUDE.md "Commands" in the root `pyproject.toml`:
  - Set `envfile = ".env"`.
  - Use only `cmd`, `script` and `sequence` tasks, never `shell`.
- Add the helper scripts in `scripts/`, in Python only:
  - `doctor.py` checks:
    - Python 3.12, uv, Node 22, pnpm, git and Docker
    - every name in `.env.example` present in `.env` (report names, never values)
    - database reachability and migration drift
    - no CRLF files in `git ls-files --eol`
    - repo not under `/mnt/c` or a synced folder
  - `machine.py`
  - `dev.py` runs services in parallel with prefixed output.
- Keep the provided `.gitignore`, `.gitattributes`, `.editorconfig`, `.python-version`, `.node-version`, `.env.example` and `.claude/`.
- Set up ruff, pyright, eslint and prettier configs, and a pre-commit hook (pre-commit installed through uv).

Done when:
- `uv run poe check` and `uv run poe doctor` pass on the empty skeleton.
- `git ls-files --eol` shows no CRLF text files.

**0.3 CI**
- `ci.yml`, on every push and PR, on Ubuntu:
  - lint, unit tests, and the web lint, typecheck and build
  - integration tests (`supabase start` from the pinned CLI)
  - the eval on recorded responses
  - Playwright e2e once it exists
  - uv and pnpm caches
- `cross-os.yml`, weekly plus manual dispatch, on a matrix of `windows-latest` and `macos-latest`:
  - `uv sync`, `uv run poe check` (unit only, no Docker), `pnpm install`, and the web build
- Container images are built for `linux/amd64` in CI only (used at 7.3).

Done when: a pull request shows green checks, and a manual `cross-os` run is green on both operating systems.

**0.4 Local Supabase (integration tests only)**
- Run `pnpm exec supabase init`, and enable the `vector` and `pgmq` extensions in the first migration.
- `poe db-up` starts only the services the tests need.
- `poe test-int` resets the local database before running.

Done when: `uv run poe db-up && uv run poe migrate --local` succeeds.

**0.5 👤 Shared dev environment**
- Apply the migrations to the hosted dev project with `uv run poe migrate`, using the Session pooler URL.
- Set the R2 dev bucket's CORS for `http://localhost:3000` and the tunnel origins.
- Add `scripts/raw_sync.py` behind `poe raw-push` and `poe raw-pull`. It syncs `data/raw/`, `evals/photos/private/` and `ingestion/reports/` with the private `R2_RAW_PREFIX`, compares checksums, and never deletes on the remote without a `--prune` flag.

Done when: `raw-push` from the first machine and `raw-pull` on the second give identical files.

**0.6 👤 Second machine and the handoff loop**
- Set up the second machine per DEV_SETUP §4 and §5.
- Do a round trip: `/handoff` on machine A, `/pickup` on machine B, a small change, `/handoff` on B, and `/pickup` on A.

Done when:
- `docs/PROGRESS.md` has an entry from each machine.
- `/pickup` reports green on both.
- Both machines see the same rows in the dev database.

---

## Phase 1: Data model and knowledge

**1.1 🧪 Core schema migration**
- Create every table from SPEC §5, plus the indexes and the `requests` and `requests_dlq` queues.

Done when: migrations apply cleanly from scratch and an integration test inserts and reads one row per table.

**1.2 🧪 `transition_request()` and the events table**
- A plpgsql function that enforces the transitions table from SPEC §6 and writes `events`.

Done when: tests cover every allowed transition and reject a sample of disallowed ones, and a direct `UPDATE requests SET status` is blocked by a trigger.

**1.3 🧪 RLS policies**
- Plant users see only their plants' requests and components. Engineers and admins see their tenant. Nobody sees another tenant.

Done when: tests impersonate the three roles across two seeded tenants and pass.

**1.4 Seed data**
- `supabase/seed/`: one tenant, two customers, three plants, about 12 components across chutes, fans, hoppers and liners, and three users (one per role).

Done when: `uv run poe seed` loads the data and the app can sign in as each user (after 5.1).

**1.5 🧪 Playbook loader**
- `packages/core/playbooks/loader.py` loads `playbooks/<id>/playbook.yaml` and validates it against a Pydantic model.
- It imports the playbook to the DB as `draft` and reads approved versions for the live pipeline.

Done when: the wear playbook loads and validates, invalid YAML fails with clear errors, and the import is idempotent.

**1.6 🧪 Rule evaluator**
- `packages/core/rules/evaluator.py`: a JSON-logic subset (`and`, `or`, `!`, `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `var` with dotted paths).
- No `eval`.

Done when: unit tests plus Hypothesis property tests cover the operators and missing variables (which evaluate to false, not an exception).

**1.7 Ingestion: parsers**
- `ingestion/parsers.py`:
  - file-type detection and text-layer detection
  - pdfplumber text and tables
  - pypdfium2 rasterization for pages without text
  - `.doc` files through LibreOffice headless, located with `SOFFICE_PATH` or `shutil.which`; a missing binary becomes an ingestion issue
- Use `pathlib` and `tempfile` only.

Done when: all 11 wear files in `data/raw/wear_protection/` produce either text or page images on **both** machines, and the report lists which path each file took.

**1.8 Ingestion: extraction and validation**
- Model extraction into `family_schema` with structured output, through the gateway (build a minimal gateway here if 3.1 isn't done yet).
- Code validators from SPEC §10 write `ingestion_issues`.

Done when: all 11 products exist as `draft` with no schema violations, and the issue list includes at least the known problems from SPEC §10.

**1.9 👤 Embeddings and the ingestion report**
- Compute text embeddings for products and image embeddings for extracted catalog photos.
- Write `ingestion/reports/wear_protection.md`.

Done when: the report renders and the human has reviewed the extracted values against the sheets. Corrections are applied by editing drafts, never by editing raw files.

---

## Phase 2: Benchmark and eval harness (do this before the pipeline)

**2.1 👤 Test set v0**
- The human photographs 15–30 worn parts or surfaces (hardware-store parts work) with known conditions.
- Write `evals/wear_protection/cases/*.yaml` per SPEC §13 and store the photos in `evals/photos/private/`.

Done when: at least 15 cases exist with expected mechanisms. Expected products can be filled in once the knowledge is approved.

**2.2 🧪 Eval harness**
- `evals/harness.py` runs a callable over the cases and computes the SPEC §13 metrics.
- It records model responses to `evals/recordings/` and replays them when `LIVE` isn't set.

Done when: a dummy predictor produces a correct report.

**2.3 Naive baseline**
- `evals/baseline/naive_rag.py`: sheet text chunks in pgvector, top-k retrieval plus the photo, answered in the same output schema.

Done when: `uv run poe eval` prints baseline metrics and the report is saved.

---

## Phase 3: Pipeline and worker

**3.1 🧪 Model gateway**
- Task-based model selection from `config/models.yaml`, temperature 0, structured output with validation and one repair retry, Langfuse tracing, and cost and latency capture.

- A `replay` provider serves recorded responses. It's the default in tests, e2e and CI.

Done when: unit tests run with the fake and replay providers, and one live smoke test runs behind `--live`.

**3.2 🧪 Contracts**
- Pydantic models for `Context`, `Evidence`, `Diagnosis`, `Recommendations`, `Checks` and `Analysis` (SPEC §7).

Done when: round-trip tests pass and JSON Schemas are exported for prompts.

**3.3 🧪 Stage 1: Context**

Done when: tests cover missing answers (leading to `needs_info`) and a component with installation history.

**3.4 🧪 Stage 2: Evidence**
- Prompt `prompts/evidence.v1.md` with the playbook vocabulary; vocabulary validation; image embeddings with open_clip.

Done when: recorded-response tests pass, unknown feature codes trigger one retry and then a failure, and an unusable photo leads to `needs_info`.

**3.5 🧪 Stage 3: Diagnosis**
- Scoring from the playbook weights, case-memory k-NN, the margin, and choosing the narrowing question.

Done when: table-driven tests cover the expected rankings for crafted evidence and the question chosen at a low margin.

**3.6 🧪 Stage 4: Remedy**
- Rules produce requirements and preferences, the database filters the candidates, and the model ranks them (candidate IDs only).

Done when: tests reject a hallucinated product ID, relax preferences but never requirements, and handle `no_candidates`.

**3.7 🧪 Stage 5: Checks**
- Implement the check registry and every check listed in the wear playbook.

Done when: each check has passing and failing tests, and a failure triggers a single Stage 4 rerun with feedback.

**3.8 🧪 Stage 6: Confidence and explanation**
- Heuristic confidence from `config/thresholds.yaml`; the explanation prompt uses only structured inputs.

Done when: tests show confidence goes up with margin and passing checks, and the `low_confidence` flag is set below the threshold.

**3.9 🧪 Orchestrator, checkpoints and cache**
- Run stages 1–6 with `pipeline_runs` checkpoints, resume, and a `cache_key` hit that reuses the analysis.

Done when: an integration test kills the run after stage 3, reruns it, and stages 1–3 aren't repeated. Running the same request twice gives one analysis.

**3.10 🧪 Worker drain and DLQ**
- Implement `POST /drain` (shared secret, time budget), loop mode for local use, the pgmq read, visibility timeout and archive, and the DLQ after `read_ct > 3`.

Done when: integration tests cover a successful run, a transient failure that recovers, and a poison message that lands in the DLQ with the request `failed`.

**3.11 Pipeline eval**
- Run the full pipeline on the test set and compare it with the baseline.

Done when: `uv run poe eval-report` shows both systems side by side. Don't tune the weights yet; just record the numbers.

---

## Phase 4: API

**4.1 🧪 Auth middleware**
- Supabase JWT verification and profile lookup. Role checks are a dependency.

Done when: tests cover valid, expired and wrong-tenant tokens.

**4.2 🧪 Uploads and request creation**
- Presigned R2 URLs; `POST /requests` saves, enqueues in the same transaction and kicks `/drain`.

Done when: an integration test goes from a created request to `ready_for_review` with a fake gateway.

**4.3 🧪 Read endpoints**
- List and detail with signed photo URLs, the timeline from `events`, and role filtering.

**4.4 🧪 Engineer actions**
- Claim and release, review (creating a `cases` row on approve or edit), messages.

Done when: tests cover two engineers claiming at once (only one succeeds) and the case row with its embeddings.

**4.5 Quotes**
- Item selection, a PDF through ReportLab, storage in R2, then `quote_sent`.

**4.6 🧪 Answers and outcomes**
- `needs_info` answers re-enqueue the request. An outcome marks the case `verified` or `flagged`.

**4.7 Knowledge admin endpoints**
- Drafts list, approve and reject (writing `approved_by` and `approved_at`, bumping the version), and the issue list.

Done when: approving the wear playbook, its rules and its products makes them visible to the pipeline. A draft is never visible.

---

## Phase 5: Frontend

**5.0 👤 Figma**
- The project settings enable the Figma plugin; authenticate it once per machine with `/mcp` (DEV_SETUP §5). Figma work happens in local sessions, because plugins don't load in cloud sessions.
- Pull frames with `get_design_context` and `get_screenshot`, and write `apps/web/DESIGN.md` mapping frames to routes and components.
- If there are no frames yet, skip this and use shadcn/ui defaults.

**5.1 App shell and auth**
- Next.js static export, Tailwind and shadcn/ui, Supabase auth with a one-time code, and role-based redirects to `/plant` or `/console`.

**5.2 Plant: home and component picker**

**5.3 Plant: guided capture**
- Camera input, the client-side blur and brightness checks, a coin confirmation, direct upload to R2.

Done when: a blurry test image triggers a retake prompt.

**5.4 Plant: conditions form**
- Rendered from the playbook questions returned by the API, with no hardcoded fields.

**5.5 Plant: status, messages, quote, follow-up**

**5.6 PWA**
- Manifest, icons, a service worker, an installable app, and an offline-friendly shell.

**5.7 Console: live queue**
- Supabase Realtime subscription, filters and claiming.

**5.8 Console: request detail**
- Photos with evidence, the diagnosis, recommendations with cited fields, checks, confidence and flags, the copilot draft, and the review actions.

**5.9 Console: quote, component history, knowledge review**

**5.10 🧪 End-to-end tests and real-device testing**
- Playwright tests in `apps/web/e2e/` on Chromium and WebKit:
  - a phone viewport for the plant flow (sign in, capture with a fixture photo, conditions, submit, see the status)
  - a desktop viewport for the console flow (live queue, review, quote)
- They run against the local stack with `MODEL_PROVIDER=replay`, behind `uv run poe e2e`. Add them to `ci.yml`.
- `scripts/phone.py` behind `poe phone`:
  - starts `cloudflared` quick tunnels for the web app and the API
  - passes the API tunnel URL as `NEXT_PUBLIC_API_URL`
  - adds the web tunnel origin to `CORS_ALLOWED_ORIGINS`
  - sets `allowedDevOrigins` for the tunnel domain
  - prints the URL to open on the phone

Done when: `uv run poe e2e` passes on the Mac and the PC.

Done when (whole phase):
- From a real phone over `poe phone`, a plant user submits a request with photos.
- The engineer sees it arrive live, in Safari on the Mac and in Edge on the PC, reviews it and sends a quote.
- The plant user sees the quote.

---

## Phase 6: Feedback loop, MCP and copilot

**6.1 🧪 Case memory retrieval in Stage 3**
- Verified cases count double, and only approved cases are used.

Done when: a test shows an approved case shifts the diagnosis for a similar photo.

**6.2 🧪 MCP server**
- The tools from SPEC §12, tenant-scoped through the service token, read-only except `save_copilot_draft`.

Done when: tests show a tool called with tenant A's token never returns tenant B's data.

**6.3 Copilot**
- An `analysis_ready` consumer with a cap of 8 tool calls and a cost cap. It writes `copilot_drafts`.

Done when: every analyzed request in the demo has a draft with sources.

**6.4 Follow-up**
- A `request_closed` event schedules the follow-up prompt in the plant app, for example at 30 days, configurable per playbook.

---

## Phase 7: Measure, calibrate, demo

**7.1 Eval and tuning**
- Tune the draft weights and thresholds on half the cases and evaluate on the other half.

Done when: the report shows the pipeline against the baseline on held-out cases, with no confident-but-wrong increase from the untuned run.

**7.2 Calibration**
- Once at least 50 cases exist, fit isotonic calibration for confidence and report the ECE. Below that, keep the heuristic and say so in the report.

**7.3 Deploy**
- Cloud Run services (api, worker, mcp), using images built in CI for `linux/amd64`.
- Cloud Scheduler hitting `/drain`.
- The web app on Cloudflare Pages, with a preview deployment per pull request that points at a dev API.
- A hosted Supabase **prod** project with migrations applied.

Done when: the end-to-end demo works on the deployed URLs from a phone, the Mac and the PC.

**7.4 Demo script and README**
- A 5-minute walkthrough script and a README with setup steps, architecture, and **measured** metrics only.

---

## After the MVP (not now)

- `spare_parts` playbook: machines, compatibility and purchases tables, part identification signals, and partial-code fuzzy matching.
- Interactive catalog ingestion agent; triage, insights and quality agents.
- WhatsApp intake as a second entry point to the same API.
- Other languages, ERP and CRM integration, pricing.

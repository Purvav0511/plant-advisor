# Plant Advisor: Technical Specification (v3)

This is the source of truth for what to build. `docs/PLAN.md` orders the work; `CLAUDE.md` holds the rules.

v3 (2026-10-13) applies decisions 0002–0017 in `docs/decisions/`. Where a section cites a decision, the decision note has the reasoning.

---

## 1. Problem and scope

**Who:** an industrial supplier (the *tenant*) that sells wear-protection products, consumables and parts to plants: cement, power, steel, mining.

**Problem:** when a component in a plant wears out or fails, the technician contacts the supplier. A sales engineer then goes back and forth to work out what's wrong and what to sell. That's slow, error-prone, and it misses chances to recommend longer-lasting products.

**Product:** two apps joined by a queue.
- **Plant app:** a technician picks a component, takes guided photos and answers a few questions. They see a preliminary recommendation when it's ready and can call, text or message the company's contact.
- **AI worker:** runs a fixed 7-stage diagnostic pipeline through the matching **playbook**, then drafts a diagnosis and a recommendation grounded in the tenant's approved catalog and rules.
- **Staff console:** requests arrive as **tickets**. An engineer reviews every ticket, approves or edits it, and can reason about it with a ticket chat copilot. Sales sends the quote and moves the status.
- **Feedback loop:** approved cases and real-world outcomes become searchable examples that improve future recommendations.

**MVP scope**
- One tenant and one playbook, `wear_protection`. The source data is 11 product data sheets: 9 composite wear plates and 2 hardfacing welding wires, in `data/raw/wear_protection/`.
- Plant app (PWA) and engineer console, with the full request lifecycle.
- Quotes are a PDF with no pricing automation.
- One agent: the ticket chat copilot for staff, with guardrails (§12).
- An eval harness comparing the pipeline with a naive RAG baseline (§13).

**Out of scope for the MVP:** a spare-parts playbook (needs machine data), WhatsApp intake, languages other than English, ERP or CRM integration, automated pricing and invoicing, and a native app.

---

## 2. Users and screens

| Role | Where | Can do |
|---|---|---|
| `plant_user` | Plant app (phone) | Create requests for their plants, see the plant's request history, answer questions, see the preliminary and confirmed recommendation, call, text or message the contact, view quotes, report outcomes |
| `engineer` | Console (desktop) | View the tenant's tickets, claim, review (approve, edit, reject the diagnosis and recommendations), chat with the copilot, message, see component history |
| `sales` | Console | View tickets, chat with the copilot, message, quote and move the status to `quote_sent` or `closed`. Can't approve a diagnosis |
| `admin` | Console | Everything an engineer and sales can, plus approve knowledge and proposals, manage customers, plants, users and invites |

A profile holds a **set** of roles (`profiles.roles`); one person can be both `engineer` and `sales` (decision 0006).

**Plant app screens:** Join (invite link or plant code, then email one-time code; decision 0004) · Sign in (one-time code) · Home (the plant's components and request history, shared by everyone at the plant; an empty state when there is none) · Pick component · Capture photos (guided: overview, close-up, coin for scale; instant blur and light checks; unsent drafts kept on the device) · Conditions (playbook questions) · Review and submit · Request status (timeline, preliminary or confirmed recommendation, call / text / message the contact, quote) · Follow-up ("how long has it lasted?").

**Console screens:** Tickets (priority, status, plant, age, confidence; claim) · Ticket detail, opened directly from the emailed link (photos with evidence, ranked diagnosis with evidence, recommendations with reasons and data-sheet citations, check results, confidence, ticket chat; approve, edit, ask or reject; quote and status for sales) · Quote · Component history · Knowledge review (drafted records, rules and proposals awaiting approval, plus the ingestion issue list) · Invites.

---

## 3. Architecture

```
Plant app (Next.js PWA) ──presigned PUT──▶ R2 (photos)
        │ POST /v1/requests
        ▼
FastAPI (Cloud Run) ──save + pgmq.send──▶ Supabase Postgres (requests, knowledge, pgvector, pgmq)
        │ POST /drain kick (before responding)               ▲         │ realtime
        ▼                                                    │         ▼
Worker (Cloud Run) ── 7-stage pipeline ── model gateway ──▶ paid model APIs
        │ writes analyses, status=ready_for_review           Engineer console (Next.js)
        ▼                                                         │
Ticket chat (staff) ── MCP server (read-only tools) ──────────────┘
```

**Key decisions**
- **Recommendations come from a scored diagnosis plus catalog rules, not from vector search** (decision 0002). Vector search finds similar past cases; the model only ranks candidates that pass the rules.
- **Synchronous at the edge, message-driven behind it.** The API only validates, saves, enqueues and returns a request ID. It never calls a model.
- **One worker runs all the stages as code,** with a checkpoint per stage. There's no function per stage and no Step Functions.
- **The engineer's review is a status, not a running workflow.** Requests wait in `ready_for_review`.
- **Postgres does three jobs:** the database, the vector store (pgvector) and the queue (pgmq).
- **The worker can scale to zero.** It exposes `POST /drain`, which processes messages until the queue is empty or a time budget runs out. The API sends the kick before it returns its own response (short timeout, errors ignored), because Cloud Run throttles CPU after a response. A scheduler pings `/drain` every minute to recover anything missed (decision 0009). For local development, `uv run poe worker` runs a polling loop.
- **Events become consumers:** `analysis_ready` emails the ticket link to staff and makes the preliminary recommendation visible to the plant (§6); `request_closed` schedules the follow-up.
- **Portable hosting:** every service is a Docker image and the queue sits behind a `Queue` interface (pgmq now, SQS later). Cloud Run for the MVP; AWS is decided at PLAN 7.3 (decision 0009).
- **AWS equivalents for later:** SQS, ECS Fargate for the worker (the embedding model is too heavy for Lambda cold starts), Lambda for light handlers, and Step Functions only once quoting and invoicing add long multi-service workflows.

---

## 4. Playbooks

A playbook packages everything specific to one product family. Core code loads it through `packages/core/playbooks/loader.py` and never hardcodes a family.

`playbooks/<id>/playbook.yaml` contains:
- `id`, `version`, `status` (draft or approved), `question` (what the playbook answers)
- `vocabulary`: `mechanisms` (or failure modes), `visual_features`, `component_types`, `materials`, `industries`, each an item with `code`, `label`, `description`
- `questions`: technician questions (`id`, `text`, `type`, `options`, `required`, `discriminates` — the mechanisms it helps separate)
- `family_schema`: a JSON Schema for `products.attributes` in this family
- `scoring`: feature-to-mechanism weights, answer-to-mechanism weights, component priors, the case-memory weight and the question margin
- `remedy_rules`: rules from diagnosis plus conditions to **attribute requirements** and preferences, plus thickness and installation choices
- `checks`: IDs of the deterministic checks Stage 5 runs, with parameters

**Rules are data.** Conditions and actions use a small JSON-logic subset (`and`, `or`, `>=`, `<=`, `==`, `in`, `var`), evaluated by `packages/core/rules/evaluator.py`. Never use `eval`. The evaluator must have full unit tests.

**Remedies produce requirements, not product names.** For example: *if abrasion ≥ 0.5, require `wear_profile.abrasion >= 4`*. The products that meet the requirements come from a database filter, so products added later qualify automatically.

**Approval:** a playbook's YAML is imported into the `playbooks`, `vocab_terms` and `rules` tables as `draft`. An admin approves it in Knowledge review, and the live pipeline reads approved versions only.

The starter for the first playbook is `playbooks/wear_protection/playbook.yaml`. **Every weight and rule in it is a draft** until the tenant's engineers approve it.

**Second playbook (later), `spare_parts`:** identifies parts from photos combined with purchase history, the plant's machine register, visual similarity to reference photos, partial-code fuzzy matching and one discriminating question. It adds machine and compatibility tables (§5, "later").

---

## 5. Data model (Postgres)

All tables have `id uuid primary key default gen_random_uuid()` unless noted, plus `created_at timestamptz default now()`. Tenant-owned tables carry `tenant_id uuid not null`. RLS is on everywhere.

```sql
-- tenancy and people
tenants(id, name)
customers(id, tenant_id, name)                         -- the company that owns plants
plants(id, tenant_id, customer_id, name, location)
profiles(user_id uuid pk references auth.users, tenant_id, customer_id null,
         roles text[] not null check (roles <@ array['plant_user','engineer','sales','admin']),
         plant_ids uuid[] default '{}', display_name, phone text null)          -- phone: staff work number for call/text
plant_invites(id, tenant_id, customer_id, code text unique, plant_ids uuid[], roles text[],
              expires_at timestamptz, max_uses int, uses int default 0, created_by uuid)

-- assets
components(id, tenant_id, plant_id, playbook_id text, component_type text, name text,
           attributes jsonb default '{}', qr_code text unique null)
installations(id, tenant_id, component_id, product_id uuid null, description text,
              installed_on date, removed_on date null, notes text)

-- knowledge (versioned; live pipeline reads status='approved' only)
playbooks(id text, tenant_id, version int, status text check (status in ('draft','approved','retired')),
          config jsonb, family_schema jsonb, approved_by uuid null, approved_at timestamptz null,
          primary key (tenant_id, id, version))
vocab_terms(id, tenant_id, playbook_id text, kind text, code text, label text, description text,
            status text, version int, unique (tenant_id, playbook_id, kind, code, version))
products(id, tenant_id, code text not null, family text, name text, description text, applications text[],
         attributes jsonb not null default '{}', source_doc text, status text, version int,
         text_embedding vector(384), updated_at timestamptz,
         unique (tenant_id, code, version))                   -- code: stable identity across versions and DBs (0003)
product_images(id, tenant_id, product_id, r2_key text, kind text check (kind in ('catalog','used','field')),
               image_embedding vector(512))
rules(id, tenant_id, playbook_id text, kind text check (kind in ('remedy','check','compatibility')),
      name text, condition jsonb, action jsonb, rationale text, status text, version int,
      approved_by uuid null, approved_at timestamptz null)
ingestion_issues(id, tenant_id, source_doc text, product_name text, field text, issue text,
                 severity text check (severity in ('info','warning','error')), status text default 'open')

-- requests
requests(id, tenant_id, customer_id, plant_id, component_id, playbook_id text,
         status text not null default 'submitted', priority text default 'normal',
         answers jsonb default '{}', note text, created_by uuid, claimed_by uuid null,
         contact_user_id uuid null, attempt int not null default 0, updated_at timestamptz)
request_photos(id, tenant_id, request_id, r2_key text, kind text check (kind in ('overview','closeup','nameplate','other')),
               client_quality jsonb, image_embedding vector(512))
pipeline_runs(id, tenant_id, request_id, attempt int, stage text, status text,
              input_hash text, output jsonb, versions jsonb, error text,
              started_at timestamptz, finished_at timestamptz,
              unique (request_id, attempt, stage))
analyses(id, tenant_id, request_id, attempt int, evidence jsonb, diagnosis jsonb,
         recommendations jsonb, checks jsonb, confidence numeric, explanation text,
         flags text[], versions jsonb, cache_key text,
         unique (request_id, attempt))                -- one per attempt; current = requests.attempt
reviews(id, tenant_id, request_id, engineer_id, decision text check (decision in ('approved','edited','rejected')),
        final_diagnosis jsonb, final_recommendations jsonb, notes text)
messages(id, tenant_id, request_id, author_id, body text)
quotes(id, tenant_id, request_id, items jsonb, pdf_r2_key text, sent_at timestamptz)
outcomes(id, tenant_id, request_id, component_id, reported_life_days int null, resolved bool null, notes text)
cases(id, tenant_id, request_id, playbook_id text, summary text, diagnosis jsonb, product_ids uuid[],
      verified bool default false, flagged bool default false,
      image_embedding vector(512), text_embedding vector(384))      -- case memory: created only from reviews
chat_messages(id, tenant_id, request_id, author_id uuid null, role text check (role in ('user','assistant','tool')),
              body text, sources jsonb, blocked bool default false)      -- ticket chat (§12); author null = assistant
knowledge_proposals(id, tenant_id, request_id null, kind text check (kind in ('product_value','rule','weight','vocab')),
                    target jsonb, change jsonb, rationale text, proposed_by text, status text default 'open',
                    eval_report text null, decided_by uuid null, decided_at timestamptz null)
events(id bigserial primary key, tenant_id, request_id uuid null, type text, payload jsonb, created_at)
```

**Indexes:** HNSW indexes on every vector column; B-tree indexes on `(tenant_id, status)` for requests, `(tenant_id, family, status)` for products, and `(tenant_id, playbook_id, status)` for rules.

**Queues (pgmq):** `requests` and `requests_dlq`. Messages are typed: `{"type": "analyze", "request_id"}` and `{"type": "embed_case", "case_id"}` (decision 0010).

**Later (spare-parts playbook):** `machines(id, tenant_id, plant_id, model, maker, attributes)`, `product_compatibility(product_id, machine_model, notes)`, `purchases(id, tenant_id, customer_id, plant_id, product_id, qty, purchased_on)`.

---

## 6. Request lifecycle

```
submitted → analyzing → ready_for_review → in_review → quote_sent → closed
                 │  ▲                          │
                 ▼  │                          └→ closed            (rejected or no quote needed)
             needs_info                         
analyzing → failed  (after DLQ; an engineer can push it to ready_for_review manually)
```

**Allowed transitions,** enforced in `transition_request()`, which also inserts an `events` row:

| From | To | Who |
|---|---|---|
| submitted | analyzing | worker |
| analyzing | needs_info | worker |
| needs_info | analyzing | api (answers received) |
| analyzing | ready_for_review | worker |
| analyzing | failed | worker |
| failed | ready_for_review | engineer |
| ready_for_review | in_review | engineer (claim) |
| in_review | ready_for_review | engineer (release) |
| in_review | quote_sent | sales (needs an approved or edited review) |
| in_review | closed | engineer or sales |
| quote_sent | closed | sales or system |

The `in_review → ready_for_review` release is the only backward-looking move. It returns a claimed request to the queue, and it's allowed explicitly.

**Mechanics** (decision 0013): a trigger blocks direct status updates; `transition_request()` sets a transaction-local flag the trigger checks, locks the row and verifies the from-state. `requests.attempt` increments on every entry into `analyzing`; a redelivered message resumes the same attempt. If the request is already `analyzing`, the worker skips the transition.

**What the plant user sees** (decision 0005): once an analysis exists, the diagnosis and top-3 products are shown as **Preliminary, pending engineer confirmation**, and as **Confirmed** (the engineer's final version) after an approve or edit review. Products are **withheld** ("an engineer is reviewing this") when the analysis has `low_confidence`, `checks_failed` or `no_candidates`. The request shows call (`tel:`) and text (`sms:`) actions for `contact_user_id` (the tenant's on-call contact by default, then the claiming engineer) and in-app messages.

---

## 7. Pipeline (worker)

Seven stages run in order. Each one:
- reads typed input,
- writes typed output (Pydantic models in `packages/core/pipeline/contracts.py`),
- is checkpointed in `pipeline_runs`.

Only stages 2, 4 and 6 call a model. Code validates every model output before the next stage uses it.

**Determinism**
- Temperature 0, pinned model IDs, versioned prompts.
- `cache_key = sha256(photo bytes + answers + playbook_version + catalog_version + prompt_versions + model_ids)`. A cache hit reuses the analysis.

**Stage 0: Intake checks (client side, in the plant app)**
- Checks for blur (variance of the Laplacian on a downscaled canvas), brightness, and a "coin or hand visible" confirmation.
- If a check fails, the app prompts a retake. Results are stored in `request_photos.client_quality`.

**Stage 1: Context (no model)**
- Input: `request_id`.
- Output `Context`:
  - `playbook`: ID and version
  - `component`: type and attributes
  - `current_installation`: product, installation date, removal date, life in days
  - `past_requests`: the last 5 for this component
  - `answers` and `missing_required`
- Picks the playbook from `components.playbook_id`.
- If required answers are missing: transition to `needs_info` with the question IDs and stop.

**Stage 2: Evidence (model, vision)**
- Prompt `prompts/evidence.vN.md` includes the playbook vocabulary, and the model call uses structured output.
- Output `Evidence`:
  - `features[]`: `code` (must be in `vocabulary.visual_features`), `location`, `severity` 1–3, `confidence` 0–1
  - `visible_text[]`
  - `photo_quality`: `usable`, `issues[]` and `missing_views[]` (e.g. `closeup`, `scale`)
  - `notes`
- The stage also computes image embeddings (open_clip) for each photo and stores them in `request_photos.image_embedding`.
- **Validation:** unknown feature codes are rejected and the stage retries once with the error. If `photo_quality.usable` is false or a required view is missing, the request goes to `needs_info` with a specific retake request (decision 0008).

**Stage 3: Diagnosis (no model)**
- For each mechanism `m`, the raw score is the sum of:
  - over evidence features: `scoring.feature_weights[f][m] × severity/3 × confidence`
  - over answers: `scoring.answer_weights[q][a][m]`
  - `scoring.component_priors[component_type][m]`
  - `scoring.case_weight × similarity-weighted votes` from the k=5 nearest **approved** cases (image plus text embeddings; verified cases count double)
- Normalize the raw scores to 0–1 by dividing by the maximum. Also record `evidence_mass` (the sum of raw scores before normalization), which feeds confidence so thin evidence can't look certain (decision 0002).
- Output `Diagnosis`:
  - `ranked[]`: `mechanism`, `score`, `evidence_refs[]`
  - `margin`: the gap between the top two scores
  - `question_id`: null, or the question to ask
- **Narrowing:** if `margin < scoring.question_margin` and there's an unanswered question whose `discriminates` set contains both top mechanisms, set `question_id`, transition to `needs_info` and stop. Ask at most one narrowing question per request.

**Stage 4: Remedy (rules, then a model for ranking and wording)**
- Evaluate the approved remedy rules against the diagnosis and answers. That yields `requirements` (hard filters on `attributes`), `preferences` (soft ordering), `thickness` and `installation`.
- Load the approved products in the playbook's family and keep those that meet the requirements, evaluated in Python with the rule evaluator (decision 0002). If there are none, relax preferences only, never requirements. If there are still none, set the flag `no_candidates` and pass the request to Stage 6.
- The model ranks up to 8 candidates down to a top 3. Each reason must cite attribute fields such as `wear_profile.abrasion` or `max_service_temp_c`.
- Output `Recommendations`:
  - `items[]`: `product_id` (must be in the candidates), `rank`, `reason`, `cited_fields[]`
  - `thickness`, `installation`, `process_advice` (nullable: process changes such as reducing a drop height)

**Stage 5: Checks (no model)**
- Run every check listed in `playbook.checks`:
  - `product_exists_and_approved`
  - `temp_limit_ok`: `max_service_temp_c ≥ reported temperature + margin`
  - `wear_profile_covers_diagnosis`: required levels are met for every mechanism scoring ≥ 0.5
  - `format_offered`: the thickness exists in `plate_formats`
  - `no_contradiction_with_installation`: don't recommend the same product that failed fast, unless flagged
- Output `Checks`: `passed`, and `results[]` with `check`, `ok` and `detail`.
- On failure: rerun Stage 4 once with the failures as feedback. If it fails again, set the flag `checks_failed` and continue (the engineer will see it).

**Stage 6: Confidence and explanation (model for the wording only)**
- **Confidence** comes from `config/thresholds.yaml` weights over:
  - the diagnosis margin
  - the evidence mass
  - mean evidence confidence
  - photo quality
  - the checks passing
  - the top case similarity

  It's a heuristic logistic in the MVP and is calibrated with isotonic regression once the eval set is large enough (§13).
- **Explanation:** the model writes 3–5 sentences using only the structured outputs, citing photo evidence and data-sheet fields.
- Add the flag `low_confidence` below the threshold.
- Write `analyses`, transition to `ready_for_review` and emit `analysis_ready`.

**Failure handling**
- Each stage retries once on a transient error.
- After 3 deliveries (pgmq `read_ct`), the message moves to `requests_dlq` and the request moves to `failed`.

---

## 8. API (FastAPI, `/v1`)

Auth uses the Supabase JWT (verified against the project's JWKS; the project uses asymmetric signing keys). Roles and tenant come from `profiles`. Every API transaction runs `SET LOCAL ROLE authenticated` with the verified claims, so RLS applies (decision 0012).

| Method and path | Role | Purpose |
|---|---|---|
| `POST /uploads/presign` | plant_user | Returns presigned R2 PUT URLs and keys for N photos |
| `POST /requests` | plant_user | Creates a request with `component_id`, `answers`, `note`, `photos[{key, kind, client_quality}]` and `priority`; enqueues it; kicks `/drain` before responding |
| `GET /requests` | all | Lists requests, filtered by role, with `status`, `plant_id` and `mine` filters |
| `GET /requests/{id}` | all | Request, photos (signed GET URLs), analysis (for plant users, filtered per §6), messages, quote, timeline, contact |
| `POST /requests/{id}/answers` | plant_user | Answers or new photos for `needs_info`; re-enqueues |
| `POST /requests/{id}/claim` / `release` | engineer | |
| `POST /requests/{id}/review` | engineer | `decision`, `final_diagnosis`, `final_recommendations` and `notes`. On approve or edit, creates a `cases` row and enqueues `embed_case`; the worker computes the embeddings (decision 0010) |
| `GET/POST /requests/{id}/chat` | engineer, sales, admin | Ticket chat history; send a message to the copilot (§12) |
| `POST /requests/{id}/messages` | all | |
| `POST /requests/{id}/quote` | sales | Items, then generates a PDF (ReportLab, pure Python, so it works the same on every OS), stores it in R2, transitions to `quote_sent` |
| `POST /requests/{id}/outcome` | plant_user | Reported life and whether it resolved the problem. Marks the case `verified`, or `flagged` if it failed fast |
| `GET/POST /components` | plant_user, admin | The plant's register |
| `GET /knowledge/drafts` · `POST /knowledge/{type}/{id}/approve` · `POST .../reject` | admin | Products, rules, vocabulary, playbooks |
| `GET /knowledge/issues` · `POST /knowledge/issues/{id}/resolve` | admin | Ingestion issue list |
| `GET /knowledge/proposals` · `POST /knowledge/proposals` · `POST .../{id}/approve` · `.../reject` | engineer (create), admin (decide) | Knowledge change proposals; approval needs an attached eval report (§11) |
| `POST /invites` · `GET /invites` | admin | Create and list plant invites |
| `POST /invites/redeem` | signed-in user without a profile | Redeem an invite code; creates the profile bound to its plants |
| `GET /health` | none | |

---

## 9. Worker and queue mechanics

- **Enqueue:** in the same transaction that inserts the request, call `pgmq.send('requests', {"request_id": ...})`.
- **Drain loop:**
  - `pgmq.read('requests', vt => 180, qty => 1)`
  - Process the message, then `pgmq.archive`.
  - On an exception, leave the message so it becomes visible again after `vt`.
  - If `read_ct > 3`, send it to `requests_dlq`, archive the original and transition the request to `failed`.
- `/drain` is authenticated with a shared secret header and has a time budget of about 8 minutes.
- **Resume:** before each stage, check `pipeline_runs` for a successful row with the same `input_hash` and reuse its output.
- **Message types:** `analyze` runs the pipeline; `embed_case` computes a case's embeddings (image: mean of the request's photo embeddings; text: the case summary).

---

## 10. Knowledge ingestion (`ingestion/`)

**Inputs:** `data/raw/<family>/`, which can contain text PDFs, scanned PDFs (no text layer), and `.doc` or `.docx` files.

**Steps**
1. **Detect** the file type and whether each page has a text layer (pdfplumber character count per page).
   - Extract text and tables with pdfplumber.
   - Rasterize pages that have no text layer with pypdfium2.
   - Convert `.doc` files with LibreOffice headless, which is found via `SOFFICE_PATH` or `PATH`. If LibreOffice is missing, write an `ingestion_issues` row asking for a PDF instead of failing.
   - Every tool here is cross-platform, and paths are handled with `pathlib`.
2. **Extract** with the model: page text, plus page images where there's no text layer or the content is tabular or visual (for example the five-level wear-resistance chart). The output is a record matching `playbook.family_schema`, through structured output.
3. **Validate** with code:
   - JSON Schema compliance
   - each range has min ≤ max
   - element percentages fall within 0–100
   - HRC falls within 20–75
   - temperatures fall within 0–1500 °C

   Every anomaly is written to `ingestion_issues`, such as a missing composition table or a suspicious range like "0.40 – 75".
4. **Write** `products` rows as `draft`, embed `name + description + applications` for `text_embedding`, and extract embedded product photos to `product_images` (`kind = 'catalog'`).
5. **Report:** `ingestion/reports/<family>.md` lists the records created and the open issues, ready to send to the tenant.

**Known state of the wear data (11 sheets):**
- Three template styles; 2 scanned PDFs and 1 `.doc` file.
- 5 sheets have composition headers without values.
- One wire sheet has a suspicious carbon range.
- One plate sheet has only a test report, with no description or applications.
- Only 2 sheets carry the five-level wear scale. The others need engineer input, or a draft wear profile inferred from their text and marked `inferred: true`.

---

## 11. Feedback loop and case memory

- **Automatic, gated by engineer approval:** an approved or edited review creates a `cases` row with diagnosis, products and embeddings. Unreviewed AI output never enters case memory.
- **Outcomes:** a resolved outcome marks the case `verified`, which gets double weight in Stage 3. Failing fast (life below the playbook's threshold) marks it `flagged` and opens a rule-review item.
- **Reviewed changes:** rule, weight, vocabulary and product-value changes are written as `knowledge_proposals`, by engineers, by the ticket chat, and later by the quality agent. The chat never changes knowledge directly (decision 0007). They must pass `uv run poe eval` with no increase in the confident-but-wrong rate before an admin approves them. Everything is versioned and can be rolled back.
- **Isolation:** case memory is per tenant. There's no cross-tenant retrieval.

---

## 12. Agents and MCP

**MCP server (`services/mcp`, read-only except for drafts):** every tool takes the caller's tenant from the service token.
- `search_products(query, filters)`
- `get_product(id)`
- `get_component_history(component_id)`
- `get_installations(component_id)`
- `find_similar_cases(request_id, k)`
- `get_rules(playbook_id, mechanism?)`
- `get_analysis(request_id)`
- `propose_knowledge_change(request_id, kind, target, change, rationale)`: writes `knowledge_proposals` only, with status `open`

**Ticket chat copilot (MVP; decision 0007)**
- A chat on each ticket for staff (engineer, sales, admin), stored in `chat_messages`. Each turn is loaded with the ticket context: request, photos' evidence, analysis, checks and the component's history.
- Uses the MCP tools only, with a cap of 8 tool calls and a cost limit per message.
- Can explain and challenge the recommendation, find similar cases, draft a note to the technician, and write a knowledge proposal. It never sends anything to a customer and never changes knowledge directly.
- **Guardrails, in layers:**
  1. A cheap topic classifier rejects messages that aren't about this ticket, the products, the plant or wear; the turn is stored with `blocked = true` and a fixed reply.
  2. A ticket-scoped system prompt. Photos, documents, messages and tool results are data, never instructions.
  3. Read-only, tenant-scoped tools; `propose_knowledge_change` is the only write.
  4. Code validates the answer: every product ID or code it mentions must exist and be approved, and every citation must resolve.
  5. Caps on tool calls and cost per message; everything traced in Langfuse.

**Later agents:** catalog ingestion as an interactive agent, triage (urgency, routing, duplicates), follow-up scheduling, weekly insights, and the quality agent (nightly eval plus rule proposals). They all start in "draft" mode.

**Model gateway (`packages/core/models/gateway.py`)**
- `complete(task, messages, schema=None, images=None) -> parsed`
- Picks the model per task from `config/models.yaml`, enforces temperature 0, and validates structured output.
- Logs to Langfuse and records cost and latency.
- One provider is implemented first, with the interface ready for others.

---

## 13. Evaluation

**Test set:** `evals/wear_protection/cases/<id>.yaml`

```yaml
id: wp-0001
photos: [assets/eval-photos/wp-0001-a.jpg]
component_type: chute
answers: {material_handled: clinker, temperature: ambient, wet_or_dry: dry, particle_size: lumps, impact: high, life_of_current_days: 60}
expected:
  mechanisms_top2: [abrasion, impact]        # either order
  acceptable_products: ["<product code>"]   # products.code (decision 0003)
  must_not_recommend: []
source: own_photo | client_case | synthetic_ui_only
```

**Sources:**
- Your own photos of worn parts, with answers you know. These are committed under `assets/eval-photos/` (JPEG, long side ≤ 1600 px), so CI can run the eval (decision 0011).
- Client photos stay in `evals/photos/private/` (gitignored); their cases run locally only.
- Client site reports and case studies, once received.
- Synthetic images are never used for accuracy.

**Metrics** (`evals/harness.py`):
- Mechanism top-1 and top-2 accuracy
- Recommendation top-3 hit rate
- **Confident-but-wrong rate:** confidence ≥ threshold and wrong
- Hand-off rate
- Expected calibration error
- p50 and p95 latency
- Cost per request

**Baseline (`evals/baseline/naive_rag.py`):** data-sheet text chunks go into pgvector, the model gets the top-k chunks plus the photo, and it answers in the same output schema. It runs on the same cases.

**Gate:** CI runs the eval on recorded responses. A change that raises the confident-but-wrong rate or lowers top-3 accuracy beyond tolerance fails CI. Reports go in `evals/reports/`.

---

## 14. Frontend

- **One Next.js app,** built as a static export, with route groups `(plant)` and `(console)` and role-based redirects after sign-in. Detail pages use query strings (`/console/request?id=…`), because a static export can't have unknown dynamic segments (decision 0014).
- **Plant app:**
  - Phone-first PWA (manifest and service worker) with large touch targets.
  - Camera capture through `<input type="file" accept="image/*" capture="environment">` plus client-side checks on a canvas.
  - Direct upload to R2 with presigned URLs.
  - Questions rendered from the playbook's `questions` (fetched from the API), so a new playbook needs no UI code.
- **Console:**
  - The queue updates live through Supabase Realtime on `requests`.
  - Ticket detail shows photos with evidence locations, the ranked diagnosis, recommendations with cited fields, check results, confidence, flags, the ticket chat and actions.
- **Plant request status** shows the preliminary or confirmed recommendation per §6, with call, text and message actions.
- **Figma first** (decision 0016): every screen is designed in Figma before it's built; colours, type and spacing become Tailwind theme tokens. Once the Figma MCP server is connected, pull frames with `get_design_context` and `get_screenshot`, map them to components, and match the spacing and type. Until designs exist, build with shadcn/ui following the screen list in §2.
- **Testing:**
  - Playwright e2e runs on Chromium and WebKit, with phone viewports for `/plant` and desktop for `/console`. It runs against the local stack with `MODEL_PROVIDER=replay`, so results are identical on every machine.
  - Real-device checks: Safari (Mac), Edge (PC), and a real phone over an HTTPS tunnel (`uv run poe phone`), because camera capture and the service worker need HTTPS.
  - In development, `next.config` sets `allowedDevOrigins` to include the tunnel domain.

---

## 15. Security and privacy

- RLS on every table, keyed on `tenant_id` and the roles and plants from `profiles`. The API runs under RLS (`SET LOCAL ROLE authenticated`); only the worker and MCP use the service role, always with an explicit tenant filter.
- The ticket chat's guardrails are in §12.
- Photos are private in R2. Access goes through short-lived signed URLs.
- Client documents and photos go only to paid model endpoints that don't train on the data. No free-tier APIs with real data.
- The audit trail lives in `events`, `pipeline_runs`, `reviews` and `analyses.versions`.
- Secrets live in environment variables, with `.env.example` committed.

---

## 16. Stack, hosting and environment

| Layer | MVP (free tier) | Later |
|---|---|---|
| Web | Next.js static export on Cloudflare Pages (Vercel's free plan is non-commercial) | Paid hosting |
| API, worker, MCP | Docker containers on Google Cloud Run (scale to zero) | Paid Cloud Run, or AWS (Lambda + SQS, or ECS Fargate), decided at 7.3 (decision 0009) |
| Database, auth, realtime, vectors, queue | Supabase free (the project pauses after 7 days idle) | Supabase Pro |
| Photos | Cloudflare R2 free (no egress fees) | Paid R2 |
| Scheduler | Cloud Scheduler hitting `/drain` every minute | Same |
| Email (sign-in codes, ticket links) | Supabase's built-in email in dev; Resend free tier before the pilot | Paid |
| Models | Paid API through the gateway | Volume pricing, own models |
| Tracing and errors | Langfuse and Sentry free tiers | Paid or self-hosted |
| CI | GitHub Actions: Ubuntu on every push; Windows and macOS weekly | Same |

**Environment variables (`.env.example` is the authoritative list):**
- Machine: `DEV_MACHINE`, `APP_ENV`
- Supabase: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWKS_URL`, `DATABASE_URL` (the Session pooler string, which works over IPv4), `DATABASE_URL_TEST` (local Supabase)
- R2: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_RAW_PREFIX`
- Models: `MODEL_PROVIDER` (`replay` for tests), `MODEL_API_KEY`
- Tracing and errors: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `SENTRY_DSN`
- Services: `API_PORT`, `WORKER_PORT`, `MCP_PORT`, `WORKER_URL`, `WORKER_DRAIN_SECRET`, `MCP_SERVICE_TOKEN`, `CORS_ALLOWED_ORIGINS`
- Email and links: `EMAIL_API_KEY`, `EMAIL_FROM`, `APP_BASE_URL`
- Optional tools: `SOFFICE_PATH`
- Frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

**Development environments** (details in `docs/DEV_SETUP.md`)

| Environment | OS and architecture | Database | Used for |
|---|---|---|---|
| Mac | macOS, arm64 on M-series | Shared hosted dev project; local Supabase for integration tests | Daily development, Safari testing |
| PC | Ubuntu in WSL2, x86_64 | Same | Daily development, Edge testing |
| Claude Code cloud session | Ubuntu 24.04, x86_64 | Local Docker Postgres, or dev with custom network access | Coding and unit tests away from a machine |
| CI (the `test` environment) | Ubuntu (every push and PR); Windows and macOS (weekly) | Local Supabase on Ubuntu | Gate for merges into `dev` and `main`; portability check |
| Dev (deployed) | Linux x86_64 containers, from the `dev` branch | Hosted dev project | Integration, demos |
| Production | Linux x86_64 containers (Cloud Run), from the `main` branch | Hosted prod project | Live |
| uat, prodtest | Added before the pilot (decision 0019) | Supabase Pro projects | Acceptance; production rehearsal |

- **Code must run on all of these** (CLAUDE.md invariant 15).
- **Container images** are built only in CI, for `linux/amd64`.
- **Client documents** sync between machines through the private R2 prefix (`poe raw-pull` / `raw-push`), never through git.

Recheck free-tier limits before a pilot; they change often.

---

## 17. Scaling path

| Stage | Changes |
|---|---|
| Pilot (one tenant, real plants) | Supabase Pro, an always-on worker or minimum instances of 1, alerts, backups |
| A few tenants | Interactive catalog ingestion agent, per-tenant settings, separate dev and prod, a dedicated queue (Pub/Sub or SQS) if needed |
| Many tenants | Separate embedding and model workers, read replicas, a trained image model for common wear patterns, SSO and audit exports |

---

## 18. Data still needed from the tenant

- The five-level wear scale for every product, the missing composition values, the corrected carbon range, and the missing product description.
- Their product selection chart, if they have one.
- Site visit reports and case studies (component, problem, product, life before and after), plus field photos. These feed the test set and seed case memory.
- Catalogs for other product families, and their machines and parts list, for the `spare_parts` playbook.

# 7. The data model

The database has 25 tables. They follow **the life of a request**: who's involved (the supplier, its customers, plants and people), what's in the plant (components), what the supplier knows (products and rules), then a request flowing through analysis, review, quote and follow-up, and finally approved work becoming memory for future requests.

The technical source is the migration in `supabase/migrations/` and SPEC §5; the rules behind it are [decision 0022](03-decisions.md#0022-the-database-itself-refuses-bad-data).

```
                         tenants (the supplier company)
          ┌──────────────┬──────┴───────┬──────────────────┐
     customers        profiles      knowledge           events (audit log)
          │          (people)    playbooks · vocab_terms
       plants                    products · product_images
          │                      rules · ingestion_issues
     components ── installations (what's fitted, and since when)
          │
       requests ──┬── request_photos
                  ├── pipeline_runs  (one checkpoint per analysis step)
                  ├── analyses       (the AI's result, one per attempt)
                  ├── reviews        (the engineer's decision) ──▶ cases (memory)
                  ├── messages · chat_messages
                  ├── quotes · outcomes
                  └── knowledge_proposals
```

## 1. Tenancy and people: who is who

| Table | What it holds | Why it's shaped this way |
|---|---|---|
| `tenants` | The supplier company using the system | Every other table has a `tenant_id`, so one database can serve several suppliers, each sealed off from the others |
| `customers` | Companies that own plants | Separates *who pays* from *where the machine is* |
| `plants` | Sites, each belonging to a customer | Requests, history and access are organized per plant |
| `profiles` | Each signed-in person: company, **roles** (a list), visible plants, phone | One person can be both engineer and sales; `plant_ids` gives a plant its shared history; `phone` powers the call and text buttons |
| `plant_invites` | Invite codes: plants, role, expiry, usage limit | How technicians join without typing plant details; the database refuses overuse |

## 2. Assets: what's in the plant

| Table | What it holds | Why |
|---|---|---|
| `components` | A specific part ("Kiln feed chute"), its type, its playbook, an optional QR code | Every request is *about a component*, so its history collects in one place |
| `installations` | What's fitted on a component, installed and removed when | How we know "the current liner lasted 60 days"; removal can't be before installation |

## 3. Knowledge: what the supplier knows

| Table | What it holds | Why |
|---|---|---|
| `playbooks` | A product family's rulebook, stored per **version** | Old analyses still name the version they used |
| `vocab_terms` | The fixed word lists (mechanisms, visual features, materials…) | The AI may only use these words |
| `products` | Each product: stable **code**, family, description, data-sheet values in `attributes` | The code never changes; attributes are flexible because each family has different fields |
| `product_images` | Catalog photos with their embeddings | "This worn part looks like…" comparisons |
| `rules` | Remedy rules, versioned, with who approved them | Rules are data, so engineers approve changes without a code release |
| `ingestion_issues` | Problems found reading data sheets | The list we send back to the client |

Every knowledge row is `draft`, `approved` or `retired`, and **the live system reads `approved` rows only.** Nothing extracted by AI is used until an engineer approves it.

## 4. Requests: the main flow

| Table | What it holds | Why |
|---|---|---|
| `requests` | One request: component, plant, answers, **status** (8 allowed values), priority, claimer, contact, `attempt` | `attempt` counts analysis runs, e.g. after the technician answers a follow-up question |
| `request_photos` | Each photo's storage key, kind, phone quality check, embedding | Files live in R2; the database keeps the reference and analysis data |
| `pipeline_runs` | One row per analysis step per attempt | Checkpoints: a crashed run resumes where it stopped; the same step can't run twice |
| `analyses` | The AI's result for **each attempt**: diagnosis, recommendations, checks, confidence, flags, versions used | Re-analysis adds a row and never replaces one, so every result stays explainable. The current one matches `requests.attempt` |
| `reviews` | The engineer's decision and final version | The AI's draft and the human's final answer are kept apart |
| `messages` | Technician ↔ staff messages | — |
| `chat_messages` | The ticket chat with the AI, including blocked off-topic attempts | Never mixed with customer communication |
| `quotes` | Quote items and the PDF | — |
| `outcomes` | How long the product lasted; whether it solved the problem | Good outcomes strengthen future recommendations |
| `cases` | Approved reviews as searchable examples | Only from engineer reviews, never from raw AI output |
| `knowledge_proposals` | Suggested corrections, with status and eval report | How the system learns without the chat changing anything directly |
| `events` | Append-only log: "created", "status changed", "analysis ready"… | The audit trail, and the trigger for emails and follow-ups |

## How a request's status changes

Only through one database function, `transition_request()`, the gatekeeper:
1. It works out **who's asking** from their login (or the worker naming itself).
2. It **locks the request**, so two engineers claiming at once take turns, and only the first succeeds.
3. It checks the **move is in the spec's table** (no `submitted → quote_sent`).
4. It checks **this caller may make it** (only sales or admins send quotes; only the claimer or an admin releases).
5. It checks **preconditions** (a quote needs an approved or edited review).
6. It **makes the change**: a new attempt when analysis restarts; a claim records the engineer.
7. It **logs an event**: from, to, who, why.

Nothing else can change a status. People lack permission to do it directly, and the database refuses any direct change from server code too. A new request must start as `submitted`, and its creation is logged automatically.

## Who sees what

Nobody ever sees another supplier's rows. Within a supplier:

| Data | Staff (engineer, sales, admin) | Technician (plant user) |
|---|---|---|
| Supplier, customers, plants | All | Their plants and the customer owning them |
| People | Everyone at the supplier | Themselves, and the staff on their requests (contact, claimer, message authors) |
| Invites | Admins only | — |
| Components, installations | All | Those at their plants |
| Products, playbooks, vocabulary | All, including drafts | **Approved only** |
| Rules, ingestion issues | All | — |
| Requests, photos, messages, quotes, outcomes | All | Every request at their plants (shared history) |
| Timeline (events) | All | Creation and status changes of their plants' requests |
| AI analyses, reviews, pipeline steps, case memory, AI chat, proposals | All | — (a filtered view comes through the app) |

For now, signed-in people can only **read**; each API feature adds exactly the changes it needs. Browsers can't reach the tables directly at all: everything goes through our API ([decision 0023](03-decisions.md#0023-who-can-see-and-change-what)).

## The thinking behind it

1. **The database refuses bad data itself.** Links are checked, statuses only accept listed values, confidence stays between 0 and 1. No bug or script can break these rules.
2. **Company isolation is built into the links.** A link checks that the parent row exists **and belongs to the same supplier**: the second lock, after the access rules (PLAN 1.3).
3. **Nothing important is deleted.** Things are retired with a status; history stays complete.
4. **Versions wherever knowledge can change,** so every past analysis points at what it actually used.
5. **Fixed columns for what we filter on; flexible JSON for what varies by product family,** so a new family needs no database redesign.
6. **Every analysis is reproducible:** step inputs and outputs in `pipeline_runs`, versions in `analyses.versions`, every attempt kept.
7. **Locked by default:** row-level security is on everywhere; access is opened deliberately in PLAN 1.3.

## Known trade-offs

| Choice | Trade-off |
|---|---|
| `playbook_id` on components and requests isn't a checked link | Playbooks are versioned, components name one without a version; the pipeline checks the name instead |
| `cases.product_ids` is a list | The database can't check each product in it; the code creating cases must |
| Users with history can't be deleted | Good for audit; a deletion request would need anonymizing |
| Priority is `low` / `normal` / `high` | Chosen here (the spec only gave the default); easy to change before use |

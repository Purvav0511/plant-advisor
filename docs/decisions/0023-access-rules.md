# 0023: Who can read and change what (rights and row-level security)

**Context:** since 1.1, row-level security was on everywhere with no policies (closed). Supabase also grants every right on every table to `anon` and `authenticated` by default, including rights RLS doesn't cover (TRUNCATE, REFERENCES, TRIGGER, Postgres 17's MAINTAIN), and serves our tables to browsers through its Data API (PostgREST and GraphQL), which would bypass our API's validation. Decided with the owner in PLAN 1.3.

**Decision**
- **One door.** The Data API is off on every project (local `config.toml`; dashboard "Enable Data API" on hosted, checked by `poe doctor`). Browsers only sign in and receive live updates; every read and write goes through our API.
- **Rights:** `anon` has none. `authenticated` may only `SELECT`; RLS decides the rows. `service_role` (worker, MCP) reads and writes rows but can't truncate, maintain or alter, and updates `requests` only outside the lifecycle columns. New tables, sequences and functions start closed (default privileges). Only `transition_request()` is callable by signed-in users.
- **Writes come per API task:** each endpoint (PLAN 4.x) adds exactly the grants and write policies it needs, with tests, instead of guessing them now.
- **Read policies** (all limited to the caller's own supplier first): staff (engineer, sales, admin) see everything at their supplier; plant users see their plants, the customer owning them, components and installations there, every request at those plants with its photos, messages, quotes, outcomes and timeline (creation and status changes only), and **approved** knowledge only. Plant users see only themselves and the staff on their plants' requests (contact, claimer, message authors). Invites are admin-only. Analyses, reviews, pipeline runs, cases, the ticket chat, knowledge proposals, rules and ingestion issues are staff-only; plant users get a filtered view of the analysis through the API (PLAN 4.3, invariant 13).
- **Helpers** in a `private` schema (`my_tenant`, `my_roles`, `my_plants`, `is_staff`, `is_admin`, `staff_on_my_requests`, `is_my_plants_request`) read profiles with the owner's rights, so policies stay one line and don't loop. Policies call them as `(select …)`, Supabase's recommended pattern for speed.

**Why:** least privilege, one validated entry point, and a database that enforces who sees what even if application code has a bug.

**Alternatives:** keep the Data API with write policies safe for direct browser use (more surface, two places validating writes); show plant users all staff (simpler, exposes the staff list); design every write policy now (guesswork before the endpoints exist).

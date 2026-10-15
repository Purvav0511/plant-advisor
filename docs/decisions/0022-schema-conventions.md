# 0022: Schema conventions

**Context:** SPEC §5 lists the tables and columns but not the relationships, allowed values or delete behaviour. With precision first, the database should refuse bad data itself instead of trusting every code path.

**Decision**
- **Every reference is a foreign key.** References between tenant-owned tables are **composite** `(tenant_id, x_id)`, backed by `unique (tenant_id, id)` on the parent, so a row can never point at another tenant's row. References to people go to `profiles (tenant_id, user_id)`, so a reviewer or author is always from the same tenant.
- **No cascading deletes.** Deleting a row that anything refers to is refused. Things are retired through a status, never erased, so the audit trail (SPEC §15) stays whole. User deletion is handled later (deactivate, then anonymize if required).
- **Allowed values are checks:** request status (SPEC §6), priority (`low`, `normal`, `high`), knowledge status (`draft`, `approved`, `retired`), pipeline stage and run status, issue and proposal status, `confidence` between 0 and 1, non-negative counts and life, invite `uses <= max_uses`, at least one valid role.
- **`playbook_id` is not a foreign key:** playbooks are keyed by `(tenant_id, id, version)`, and components and requests name a playbook, not a version. The pipeline resolves the approved version.
- **Row-level security is enabled on every table now, with no policies** (PLAN 1.3 adds them): closed by default.
- **One analysis per attempt,** unique on `(request_id, attempt)`. Re-analysis adds a row and never replaces one, so every result stays explainable; the current one is where `attempt = requests.attempt`. (Owner's choice during review; SPEC §5 updated.)
- **`updated_at` is maintained by a trigger** on `requests` and `products`.
- **Embeddings:** `extensions.vector(384)` (text) and `vector(512)` (image), each with an HNSW index using cosine distance. **Events** use an identity column (`bigint generated always`) instead of `bigserial`.

**Why:** a bug in one endpoint, script or migration can't create cross-tenant links, impossible states or orphaned rows; the database refuses them.

**Alternatives:** plain single-column foreign keys (simpler, but allow cross-tenant links); validation in application code only (every path must remember it); soft deletes with `deleted_at` everywhere (more complexity than the MVP needs; statuses already cover retirement).

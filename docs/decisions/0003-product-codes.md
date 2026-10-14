# 0003: Products have a stable `code`

**Context:** a product's `id` changes with every approved version and differs between the local DB, the dev DB and CI. Eval cases and checks need a stable reference.

**Decision:** add `products.code` (slug, e.g. `wp-<name>`), unique on `(tenant_id, code, version)`. Eval cases (`acceptable_products`, `must_not_recommend`), the `no_contradiction_with_installation` check and case memory compare by `code`. Recommendations still store `product_id` for the exact version used.

**Why:** reproducible evals across every database, and history survives re-versioning.

**Alternatives:** keep UUIDs and remap per DB (fragile); make the name the key (names get corrected during ingestion).

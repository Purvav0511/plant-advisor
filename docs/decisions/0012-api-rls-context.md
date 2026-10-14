# 0012: The API runs queries under RLS

**Context:** the API connects with psycopg as the database owner, which bypasses RLS.

**Decision:** every API transaction runs `SET LOCAL ROLE authenticated` and `set_config('request.jwt.claims', <verified claims>, true)` before any query, so RLS applies; queries still filter `tenant_id` explicitly. Only the worker and the MCP server use the service role, always with an explicit tenant filter. The Supabase project must use asymmetric JWT signing keys so `SUPABASE_JWKS_URL` serves them.

**Alternatives:** query through PostgREST with the user's JWT (loses transactions with `pgmq.send`).

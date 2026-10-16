# 0013: How status transitions and pipeline attempts work

**Decision**
- A trigger blocks direct `UPDATE requests SET status`. `transition_request()` sets a transaction-local flag (`set_config('app.transition','on',true)`) that the trigger checks.
- `transition_request()` locks the row (`SELECT … FOR UPDATE`) and checks the from-state, so two engineers claiming at once can't both succeed.
- `attempt` increments each time a request enters `analyzing` (from `submitted` or `needs_info`). A redelivered message resumes the same attempt from its checkpoints.
- If the request is already `analyzing` (redelivery), the worker skips the transition instead of failing.

**Update (2026-10-15, PLAN 1.2, decided with the owner):**
- **The flag alone isn't a lock:** a signed-in user could set `app.transition` themselves. So there are two locks: (1) signed-in roles lose `UPDATE` on `status`, `attempt` and `claimed_by` (table-wide `UPDATE` is replaced by column grants), and `transition_request()` runs `security definer`; (2) the trigger still refuses changes to those columns without the flag, which catches mistakes in trusted server code. The function turns the flag off again after its update.
- **Identity comes from the login token,** never a parameter: `auth.uid()` and the profile's roles for people; server code (no token, or the service key) must pass `'worker'` or `'system'`. Anonymous callers can't execute the function.
- **Who may do what:** SPEC §6's table, plus: admins may do anything engineers and sales may; release only by the claimer or an admin; `needs_info -> analyzing` only by a plant user with access to that plant; `quote_sent -> closed` also by `system`.
- **Another tenant's request is "not found"** (P0002), not "not permitted", so IDs can't be probed. Error codes: 42501 not permitted, P0001 move not allowed or precondition unmet, P0002 not found.
- **A new request must start** `submitted`, unclaimed, at attempt 0 (same trigger). **Creation is logged** as a `request_created` event by an insert trigger, so every timeline starts with it.
- One `status_changed` event per move: `{from, to, actor, actor_id, reason}`.

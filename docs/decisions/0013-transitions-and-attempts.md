# 0013: How status transitions and pipeline attempts work

**Decision**
- A trigger blocks direct `UPDATE requests SET status`. `transition_request()` sets a transaction-local flag (`set_config('app.transition','on',true)`) that the trigger checks.
- `transition_request()` locks the row (`SELECT … FOR UPDATE`) and checks the from-state, so two engineers claiming at once can't both succeed.
- `attempt` increments each time a request enters `analyzing` (from `submitted` or `needs_info`). A redelivered message resumes the same attempt from its checkpoints.
- If the request is already `analyzing` (redelivery), the worker skips the transition instead of failing.
